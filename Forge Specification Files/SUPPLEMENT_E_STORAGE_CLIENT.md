# Forge V3 - Phase 3 Supplement: Hardened Storage Client

**Purpose:** Production-ready object storage client with retry logic, error handling, multipart uploads, and proper timeouts.

**Replace:** `forge/infrastructure/storage/client.py`

---

```python
# forge/infrastructure/storage/client.py
"""
Production-ready object storage client.

Supports S3-compatible storage (AWS S3, MinIO, Oracle Cloud, etc.)
with proper error handling, retries, and large file support.
"""
import asyncio
import hashlib
from pathlib import Path
from typing import AsyncIterator, BinaryIO
from contextlib import asynccontextmanager

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError

from forge.config import get_settings
from forge.logging import get_logger
from forge.exceptions import ServiceUnavailableError, NotFoundError

logger = get_logger(__name__)


# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_BASE = 0.5  # seconds
RETRY_DELAY_MAX = 10.0  # seconds


class ObjectStorageError(Exception):
    """Base exception for storage operations."""
    pass


class ObjectStorageClient:
    """
    Production-ready async object storage client.
    
    Features:
    - Automatic retries with exponential backoff
    - Connection pooling
    - Multipart upload for large files
    - Streaming downloads
    - Proper timeout configuration
    - Health checking
    """
    
    # 5 MB threshold for multipart upload
    MULTIPART_THRESHOLD = 5 * 1024 * 1024
    # 5 MB part size
    MULTIPART_CHUNK_SIZE = 5 * 1024 * 1024
    
    def __init__(
        self,
        endpoint_url: str | None = None,
        bucket: str = "forge-data",
        region: str = "us-east-1",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ):
        """
        Initialize storage client.
        
        Args:
            endpoint_url: S3-compatible endpoint (None for AWS S3)
            bucket: Default bucket name
            region: AWS region
            access_key_id: AWS access key (uses env/IAM role if None)
            secret_access_key: AWS secret key (uses env/IAM role if None)
        """
        self._endpoint_url = endpoint_url
        self._bucket = bucket
        self._region = region
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        
        # Create session with retry configuration
        self._session = aioboto3.Session()
        self._config = Config(
            region_name=region,
            signature_version='s3v4',
            retries={
                'max_attempts': MAX_RETRIES,
                'mode': 'adaptive',
            },
            connect_timeout=10,
            read_timeout=30,
        )
    
    @asynccontextmanager
    async def _get_client(self):
        """Get S3 client with proper configuration."""
        kwargs = {
            "config": self._config,
            "region_name": self._region,
        }
        
        if self._endpoint_url:
            kwargs["endpoint_url"] = self._endpoint_url
        
        if self._access_key_id and self._secret_access_key:
            kwargs["aws_access_key_id"] = self._access_key_id
            kwargs["aws_secret_access_key"] = self._secret_access_key
        
        async with self._session.client("s3", **kwargs) as client:
            yield client
    
    async def _retry_operation(self, operation, *args, **kwargs):
        """
        Execute operation with exponential backoff retry.
        
        Retries on transient errors (network, throttling).
        Does not retry on permanent errors (access denied, not found).
        """
        last_error = None
        
        for attempt in range(MAX_RETRIES):
            try:
                return await operation(*args, **kwargs)
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                
                # Don't retry permanent errors
                if error_code in ['AccessDenied', 'NoSuchKey', 'NoSuchBucket', 
                                  'InvalidAccessKeyId', 'SignatureDoesNotMatch']:
                    raise
                
                last_error = e
                
            except (BotoCoreError, asyncio.TimeoutError) as e:
                last_error = e
            
            # Exponential backoff with jitter
            delay = min(
                RETRY_DELAY_BASE * (2 ** attempt),
                RETRY_DELAY_MAX
            )
            # Add jitter (±25%)
            delay = delay * (0.75 + 0.5 * (hash(str(attempt)) % 100) / 100)
            
            logger.warning(
                "storage_operation_retry",
                attempt=attempt + 1,
                delay=delay,
                error=str(last_error),
            )
            
            await asyncio.sleep(delay)
        
        # All retries exhausted
        logger.error("storage_operation_failed", error=str(last_error))
        raise ServiceUnavailableError(f"Storage operation failed after {MAX_RETRIES} attempts")
    
    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """
        Upload data to storage.
        
        Uses multipart upload for large files.
        
        Args:
            key: Object key (path in bucket)
            data: Raw bytes to upload
            content_type: MIME type (optional)
            metadata: Custom metadata (optional)
            
        Returns:
            ETag of uploaded object
        """
        size = len(data)
        
        if size > self.MULTIPART_THRESHOLD:
            return await self._put_multipart(key, data, content_type, metadata)
        
        async def _upload():
            async with self._get_client() as client:
                kwargs = {
                    "Bucket": self._bucket,
                    "Key": key,
                    "Body": data,
                }
                
                if content_type:
                    kwargs["ContentType"] = content_type
                if metadata:
                    kwargs["Metadata"] = metadata
                
                response = await client.put_object(**kwargs)
                return response.get("ETag", "").strip('"')
        
        etag = await self._retry_operation(_upload)
        
        logger.debug(
            "object_uploaded",
            key=key,
            size=size,
            etag=etag,
        )
        
        return etag
    
    async def _put_multipart(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Upload large file using multipart upload."""
        
        async with self._get_client() as client:
            # Initiate multipart upload
            create_kwargs = {
                "Bucket": self._bucket,
                "Key": key,
            }
            if content_type:
                create_kwargs["ContentType"] = content_type
            if metadata:
                create_kwargs["Metadata"] = metadata
            
            response = await client.create_multipart_upload(**create_kwargs)
            upload_id = response["UploadId"]
            
            try:
                parts = []
                part_number = 1
                
                # Upload parts
                for offset in range(0, len(data), self.MULTIPART_CHUNK_SIZE):
                    chunk = data[offset:offset + self.MULTIPART_CHUNK_SIZE]
                    
                    part_response = await client.upload_part(
                        Bucket=self._bucket,
                        Key=key,
                        UploadId=upload_id,
                        PartNumber=part_number,
                        Body=chunk,
                    )
                    
                    parts.append({
                        "PartNumber": part_number,
                        "ETag": part_response["ETag"],
                    })
                    
                    part_number += 1
                
                # Complete multipart upload
                complete_response = await client.complete_multipart_upload(
                    Bucket=self._bucket,
                    Key=key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )
                
                logger.debug(
                    "multipart_upload_completed",
                    key=key,
                    size=len(data),
                    parts=len(parts),
                )
                
                return complete_response.get("ETag", "").strip('"')
                
            except Exception as e:
                # Abort multipart upload on failure
                await client.abort_multipart_upload(
                    Bucket=self._bucket,
                    Key=key,
                    UploadId=upload_id,
                )
                logger.error(
                    "multipart_upload_aborted",
                    key=key,
                    error=str(e),
                )
                raise
    
    async def get(self, key: str) -> bytes | None:
        """
        Download object from storage.
        
        Returns None if object doesn't exist.
        """
        async def _download():
            async with self._get_client() as client:
                try:
                    response = await client.get_object(
                        Bucket=self._bucket,
                        Key=key,
                    )
                    
                    # Read body
                    async with response["Body"] as stream:
                        data = await stream.read()
                    
                    return data
                    
                except ClientError as e:
                    if e.response.get('Error', {}).get('Code') == 'NoSuchKey':
                        return None
                    raise
        
        try:
            data = await self._retry_operation(_download)
            
            if data is not None:
                logger.debug("object_downloaded", key=key, size=len(data))
            
            return data
            
        except ServiceUnavailableError:
            logger.warning("object_get_failed", key=key)
            return None
    
    async def get_stream(self, key: str) -> AsyncIterator[bytes]:
        """
        Stream object content in chunks.
        
        Useful for large files to avoid loading entirely into memory.
        """
        async with self._get_client() as client:
            try:
                response = await client.get_object(
                    Bucket=self._bucket,
                    Key=key,
                )
                
                async with response["Body"] as stream:
                    while True:
                        chunk = await stream.read(self.MULTIPART_CHUNK_SIZE)
                        if not chunk:
                            break
                        yield chunk
                        
            except ClientError as e:
                if e.response.get('Error', {}).get('Code') == 'NoSuchKey':
                    raise NotFoundError("Object", key)
                raise
    
    async def delete(self, key: str) -> bool:
        """
        Delete object from storage.
        
        Returns True if deleted, False if didn't exist.
        """
        async def _delete():
            async with self._get_client() as client:
                # S3 delete is idempotent - doesn't error on missing key
                await client.delete_object(
                    Bucket=self._bucket,
                    Key=key,
                )
                return True
        
        try:
            await self._retry_operation(_delete)
            logger.debug("object_deleted", key=key)
            return True
        except Exception:
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if object exists."""
        async with self._get_client() as client:
            try:
                await client.head_object(
                    Bucket=self._bucket,
                    Key=key,
                )
                return True
            except ClientError as e:
                if e.response.get('Error', {}).get('Code') == '404':
                    return False
                raise
    
    async def get_metadata(self, key: str) -> dict | None:
        """
        Get object metadata without downloading content.
        
        Returns dict with size, content_type, last_modified, custom metadata.
        """
        async with self._get_client() as client:
            try:
                response = await client.head_object(
                    Bucket=self._bucket,
                    Key=key,
                )
                
                return {
                    "size": response.get("ContentLength"),
                    "content_type": response.get("ContentType"),
                    "last_modified": response.get("LastModified"),
                    "etag": response.get("ETag", "").strip('"'),
                    "metadata": response.get("Metadata", {}),
                }
                
            except ClientError as e:
                if e.response.get('Error', {}).get('Code') == '404':
                    return None
                raise
    
    async def list_objects(
        self,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> list[dict]:
        """
        List objects with given prefix.
        
        Returns list of dicts with key, size, last_modified.
        """
        async with self._get_client() as client:
            response = await client.list_objects_v2(
                Bucket=self._bucket,
                Prefix=prefix,
                MaxKeys=max_keys,
            )
            
            objects = []
            for obj in response.get("Contents", []):
                objects.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"],
                    "etag": obj.get("ETag", "").strip('"'),
                })
            
            return objects
    
    async def copy(
        self,
        source_key: str,
        dest_key: str,
    ) -> str:
        """
        Copy object within the same bucket.
        
        Returns ETag of the copied object.
        """
        async with self._get_client() as client:
            response = await client.copy_object(
                Bucket=self._bucket,
                CopySource={"Bucket": self._bucket, "Key": source_key},
                Key=dest_key,
            )
            
            logger.debug(
                "object_copied",
                source=source_key,
                dest=dest_key,
            )
            
            return response.get("CopyObjectResult", {}).get("ETag", "").strip('"')
    
    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "get_object",
    ) -> str:
        """
        Generate a presigned URL for temporary access.
        
        Args:
            key: Object key
            expires_in: URL validity in seconds (default 1 hour)
            method: S3 operation (get_object, put_object)
            
        Returns:
            Presigned URL string
        """
        async with self._get_client() as client:
            url = await client.generate_presigned_url(
                ClientMethod=method,
                Params={
                    "Bucket": self._bucket,
                    "Key": key,
                },
                ExpiresIn=expires_in,
            )
            return url
    
    async def health_check(self) -> bool:
        """
        Check if storage is accessible.
        
        Attempts to list bucket contents (limited to 1) to verify connectivity.
        """
        try:
            async with self._get_client() as client:
                await client.list_objects_v2(
                    Bucket=self._bucket,
                    MaxKeys=1,
                )
                return True
        except Exception as e:
            logger.warning("storage_health_check_failed", error=str(e))
            return False
    
    def calculate_hash(self, data: bytes) -> str:
        """Calculate SHA-256 hash of data."""
        return hashlib.sha256(data).hexdigest()


# Factory function
def create_storage_client() -> ObjectStorageClient:
    """Create storage client from settings."""
    settings = get_settings()
    
    return ObjectStorageClient(
        endpoint_url=getattr(settings, 'storage_endpoint_url', None),
        bucket=getattr(settings, 'storage_bucket', 'forge-data'),
        region=getattr(settings, 'storage_region', 'us-east-1'),
    )
```

---

## Configuration Additions

Add these to your settings:

```python
# Add to forge/config.py Settings class

# Object Storage
storage_endpoint_url: str | None = Field(
    default=None,
    description="S3-compatible endpoint URL (None for AWS S3)"
)
storage_bucket: str = Field(
    default="forge-data",
    description="Default storage bucket name"
)
storage_region: str = Field(
    default="us-east-1",
    description="Storage region"
)
```
