"""
VCF Parser Service

Parses VCF (Variant Call Format) files to extract genetic variants.
"""

import gzip
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import structlog

from .models import (
    GeneticTestResult,
    GeneticVariant,
    VariantPathogenicity,
    VariantType,
    Zygosity,
)

logger = structlog.get_logger(__name__)


@dataclass
class VCFHeader:
    """Parsed VCF header information."""

    file_format: str = "VCFv4.2"
    reference: str | None = None
    contigs: list[str] | None = None
    info_fields: dict[str, dict[str, str]] | None = None
    format_fields: dict[str, dict[str, str]] | None = None
    sample_names: list[str] | None = None
    filters: dict[str, str] | None = None

    def __post_init__(self) -> None:
        self.contigs = self.contigs or []
        self.info_fields = self.info_fields or {}
        self.format_fields = self.format_fields or {}
        self.sample_names = self.sample_names or []
        self.filters = self.filters or {}


class VCFParser:
    """
    Parser for VCF files.

    Supports:
    - VCF 4.0, 4.1, 4.2, 4.3
    - Gzipped VCF files
    - Multi-sample VCFs
    - Common INFO annotations (gene, consequence, etc.)
    """

    # Regex for parsing INFO field metadata
    INFO_META_PATTERN = re.compile(
        r"##INFO=<ID=(?P<id>[^,]+),Number=(?P<number>[^,]+),"
        r'Type=(?P<type>[^,]+),Description="(?P<desc>[^"]*)"'
    )

    # Regex for parsing FORMAT field metadata
    FORMAT_META_PATTERN = re.compile(
        r"##FORMAT=<ID=(?P<id>[^,]+),Number=(?P<number>[^,]+),"
        r'Type=(?P<type>[^,]+),Description="(?P<desc>[^"]*)"'
    )

    def __init__(
        self,
        min_quality: float = 20.0,
        min_depth: int = 10,
        include_filtered: bool = False,
    ):
        """
        Initialize the VCF parser.

        Args:
            min_quality: Minimum quality score to include
            min_depth: Minimum read depth to include
            include_filtered: Include variants that failed filters
        """
        self.min_quality = min_quality
        self.min_depth = min_depth
        self.include_filtered = include_filtered

    def parse_file(
        self,
        file_path: str | Path,
        sample_name: str | None = None,
    ) -> GeneticTestResult:
        """
        Parse a VCF file and return all variants.

        Args:
            file_path: Path to VCF file (may be gzipped)
            sample_name: Specific sample to extract (for multi-sample VCFs)

        Returns:
            GeneticTestResult with all variants
        """
        file_path = Path(file_path)
        variants = []
        header = None
        sample_idx = 0

        # Use context manager for proper resource cleanup
        opener = gzip.open if file_path.suffix == ".gz" else open
        with opener(file_path, "rt", encoding="utf-8") as file_handle:
            # Parse header first
            header = self._parse_header(file_handle)

            # Find sample index
            if sample_name and header.sample_names:
                if sample_name in header.sample_names:
                    sample_idx = header.sample_names.index(sample_name)
                else:
                    logger.warning(
                        "vcf_sample_not_found", requested=sample_name, available=header.sample_names
                    )

            # Parse variants
            for variant in self._parse_variants(file_handle, header, sample_idx):
                variants.append(variant)

            logger.info(
                "vcf_parsed",
                file=str(file_path),
                total_variants=len(variants),
                samples=len(header.sample_names) if header.sample_names else 0,
            )

        # Create result
        pathogenic = [v for v in variants if v.is_pathogenic_or_likely()]
        vous = [
            v for v in variants if v.pathogenicity == VariantPathogenicity.UNCERTAIN_SIGNIFICANCE
        ]

        return GeneticTestResult(
            test_id=file_path.stem,
            patient_id=sample_name or (header.sample_names[0] if header.sample_names else None),
            variants=variants,
            pathogenic_variants=pathogenic,
            vous_variants=vous,
            genes_tested=list({v.gene_symbol for v in variants if v.gene_symbol}),
        )

    def parse_string(self, vcf_content: str) -> list[GeneticVariant]:
        """Parse VCF content from a string."""
        from io import StringIO

        file_handle = StringIO(vcf_content)

        header = self._parse_header(file_handle)
        return list(self._parse_variants(file_handle, header, 0))

    def _parse_header(self, file_handle: TextIO) -> VCFHeader:
        """Parse VCF header section."""
        header = VCFHeader()

        for line in file_handle:
            line = line.strip()

            if line.startswith("##fileformat="):
                header.file_format = line.split("=")[1]

            elif line.startswith("##reference="):
                header.reference = line.split("=")[1]

            elif line.startswith("##contig="):
                # Extract contig ID
                match = re.search(r"ID=([^,>]+)", line)
                if match and header.contigs is not None:
                    header.contigs.append(match.group(1))

            elif line.startswith("##INFO="):
                match = self.INFO_META_PATTERN.match(line)
                if match and header.info_fields is not None:
                    header.info_fields[match.group("id")] = {
                        "number": match.group("number"),
                        "type": match.group("type"),
                        "description": match.group("desc"),
                    }

            elif line.startswith("##FORMAT="):
                match = self.FORMAT_META_PATTERN.match(line)
                if match and header.format_fields is not None:
                    header.format_fields[match.group("id")] = {
                        "number": match.group("number"),
                        "type": match.group("type"),
                        "description": match.group("desc"),
                    }

            elif line.startswith("##FILTER="):
                match = re.search(r'ID=([^,>]+).*Description="([^"]*)"', line)
                if match and header.filters is not None:
                    header.filters[match.group(1)] = match.group(2)

            elif line.startswith("#CHROM"):
                # Column header line
                fields = line.split("\t")
                if len(fields) > 9:
                    header.sample_names = fields[9:]
                break

            elif not line.startswith("#"):
                # End of header
                break

        return header

    def _parse_variants(
        self,
        file_handle: TextIO,
        header: VCFHeader,
        sample_idx: int,
    ) -> Iterator[GeneticVariant]:
        """Parse variant records from VCF."""
        for line in file_handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            try:
                variant = self._parse_variant_line(line, header, sample_idx)
                if variant and self._passes_filters(variant, line):
                    yield variant
            except (ValueError, KeyError, IndexError) as e:
                logger.warning("vcf_variant_parse_error", error=str(e), line=line[:100])

    def _parse_variant_line(
        self,
        line: str,
        header: VCFHeader,
        sample_idx: int,
    ) -> GeneticVariant | None:
        """Parse a single variant line."""
        fields = line.split("\t")
        if len(fields) < 8:
            return None

        chrom = fields[0]
        pos = int(fields[1])
        variant_id = fields[2] if fields[2] != "." else None
        ref = fields[3]
        alt = fields[4]
        qual = float(fields[5]) if fields[5] != "." else None
        fields[6]
        info = fields[7]

        # Skip multi-allelic for now (could split)
        if "," in alt:
            alt = alt.split(",")[0]

        # Parse INFO field
        info_dict = self._parse_info(info)

        # Determine variant type
        var_type = self._determine_variant_type(ref, alt)

        # Parse sample genotype if available
        zygosity = Zygosity.UNKNOWN
        read_depth = None
        if len(fields) > 9 and header.format_fields:
            format_keys = fields[8].split(":")
            sample_values = (
                fields[9 + sample_idx].split(":") if len(fields) > 9 + sample_idx else []
            )
            sample_data = dict(zip(format_keys, sample_values, strict=False))

            # Extract zygosity from GT
            gt = sample_data.get("GT", "")
            zygosity = self._parse_genotype(gt)

            # Extract depth from DP
            if "DP" in sample_data:
                try:
                    read_depth = int(sample_data["DP"])
                except ValueError:
                    pass

        return GeneticVariant(
            chromosome=chrom,
            position=pos,
            ref_allele=ref,
            alt_allele=alt,
            variant_id=variant_id,
            gene_symbol=info_dict.get("GENE") or info_dict.get("ANN_Gene"),
            variant_type=var_type,
            zygosity=zygosity,
            quality_score=qual,
            read_depth=read_depth,
            allele_frequency=self._parse_float(info_dict.get("AF")),
            pathogenicity=self._parse_pathogenicity(info_dict),
            clinvar_id=info_dict.get("CLNID"),
            hgvs_c=info_dict.get("HGVS_C") or info_dict.get("ANN_HGVS_c"),
            hgvs_p=info_dict.get("HGVS_P") or info_dict.get("ANN_HGVS_p"),
            consequence=info_dict.get("CSQ") or info_dict.get("ANN_Consequence"),
            impact=info_dict.get("IMPACT") or info_dict.get("ANN_Impact"),
            sift_score=self._parse_float(info_dict.get("SIFT")),
            polyphen_score=self._parse_float(info_dict.get("PolyPhen")),
        )

    def _parse_info(self, info: str) -> dict[str, str]:
        """Parse INFO field into dictionary."""
        result: dict[str, str] = {}
        if info == "." or not info:
            return result

        for item in info.split(";"):
            if "=" in item:
                key, value = item.split("=", 1)
                result[key] = value

                # Parse SnpEff ANN field
                if key == "ANN":
                    ann_parts = value.split("|")
                    if len(ann_parts) > 10:
                        result["ANN_Consequence"] = ann_parts[1]
                        result["ANN_Impact"] = ann_parts[2]
                        result["ANN_Gene"] = ann_parts[3]
                        result["ANN_HGVS_c"] = ann_parts[9] if len(ann_parts) > 9 else ""
                        result["ANN_HGVS_p"] = ann_parts[10] if len(ann_parts) > 10 else ""
            else:
                # Flag field (no value)
                result[item] = "true"

        return result

    def _determine_variant_type(self, ref: str, alt: str) -> VariantType:
        """Determine the type of variant."""
        len_ref = len(ref)
        len_alt = len(alt)

        if len_ref == 1 and len_alt == 1:
            return VariantType.SNV
        elif len_ref == 1 and len_alt > 1:
            return VariantType.INSERTION
        elif len_ref > 1 and len_alt == 1:
            return VariantType.DELETION
        elif len_ref > 1 and len_alt > 1:
            return VariantType.INDEL
        else:
            return VariantType.UNKNOWN

    def _parse_genotype(self, gt: str) -> Zygosity:
        """Parse genotype string to determine zygosity."""
        if not gt or gt == ".":
            return Zygosity.UNKNOWN

        # Handle phased (|) and unphased (/) separators
        sep = "|" if "|" in gt else "/"
        alleles = gt.split(sep)

        if len(alleles) != 2:
            return Zygosity.UNKNOWN

        a1, a2 = alleles
        if a1 == a2:
            if a1 == "0":
                return Zygosity.UNKNOWN  # Homozygous reference
            else:
                return Zygosity.HOMOZYGOUS
        else:
            return Zygosity.HETEROZYGOUS

    def _parse_pathogenicity(self, info: dict[str, str]) -> VariantPathogenicity:
        """Parse ClinVar clinical significance."""
        clnsig = info.get("CLNSIG", "").lower()
        info.get("CLNREVSTAT", "")

        if "pathogenic" in clnsig:
            if "likely" in clnsig:
                return VariantPathogenicity.LIKELY_PATHOGENIC
            return VariantPathogenicity.PATHOGENIC
        elif "benign" in clnsig:
            if "likely" in clnsig:
                return VariantPathogenicity.LIKELY_BENIGN
            return VariantPathogenicity.BENIGN
        elif "uncertain" in clnsig or "vus" in clnsig:
            return VariantPathogenicity.UNCERTAIN_SIGNIFICANCE

        return VariantPathogenicity.NOT_PROVIDED

    def _parse_float(self, value: str | None) -> float | None:
        """Safely parse a float value."""
        if not value or value == ".":
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _passes_filters(self, variant: GeneticVariant, line: str) -> bool:
        """Check if variant passes quality filters."""
        fields = line.split("\t")
        filter_field = fields[6] if len(fields) > 6 else "."

        # Check filter status
        if not self.include_filtered:
            if filter_field not in ["PASS", "."]:
                return False

        # Check quality
        if self.min_quality and variant.quality_score:
            if variant.quality_score < self.min_quality:
                return False

        # Check depth
        if self.min_depth and variant.read_depth:
            if variant.read_depth < self.min_depth:
                return False

        return True


# =============================================================================
# Factory Function
# =============================================================================


def create_vcf_parser(
    min_quality: float = 20.0,
    min_depth: int = 10,
    include_filtered: bool = False,
) -> VCFParser:
    """Create a VCF parser instance."""
    return VCFParser(
        min_quality=min_quality,
        min_depth=min_depth,
        include_filtered=include_filtered,
    )
