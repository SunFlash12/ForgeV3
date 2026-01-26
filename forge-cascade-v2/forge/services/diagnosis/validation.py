"""
Input Validation Module

Provides validation functions for clinical data inputs to prevent
injection attacks and ensure data quality.
"""

import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Valid patterns (case-insensitive for user convenience, ASCII-only for security)
HPO_PATTERN = re.compile(r"^HP:[0-9]{7}$", re.IGNORECASE)
MONDO_PATTERN = re.compile(r"^MONDO:[0-9]{7}$", re.IGNORECASE)
OMIM_PATTERN = re.compile(r"^[0-9]{6}$")
GENE_SYMBOL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9\-]{1,15}$")


def is_valid_hpo_code(code: str | None) -> bool:
    """
    Validate an HPO (Human Phenotype Ontology) code.

    Valid format: HP:NNNNNNN (HP: followed by 7 digits)

    Args:
        code: The HPO code to validate

    Returns:
        True if valid, False otherwise
    """
    if not code or not isinstance(code, str):
        return False
    return bool(HPO_PATTERN.match(code.strip()))


def is_valid_disease_id(disease_id: str | None) -> bool:
    """
    Validate a disease identifier (MONDO or OMIM).

    Valid formats:
    - MONDO:NNNNNNN
    - NNNNNN (OMIM)

    Args:
        disease_id: The disease ID to validate

    Returns:
        True if valid, False otherwise
    """
    if not disease_id or not isinstance(disease_id, str):
        return False
    disease_id = disease_id.strip()
    return bool(MONDO_PATTERN.match(disease_id) or OMIM_PATTERN.match(disease_id))


def is_valid_gene_symbol(symbol: str | None) -> bool:
    """
    Validate a gene symbol.

    Valid format: 2-16 alphanumeric characters, starting with letter,
    may contain hyphens (e.g., BRCA1, HLA-DRB1, TP53)

    Args:
        symbol: The gene symbol to validate

    Returns:
        True if valid, False otherwise
    """
    if not symbol or not isinstance(symbol, str):
        return False
    return bool(GENE_SYMBOL_PATTERN.match(symbol.strip()))


def sanitize_hpo_codes(codes: list[Any]) -> list[str]:
    """
    Filter and sanitize a list of HPO codes.

    Args:
        codes: List of potential HPO codes

    Returns:
        List of valid HPO codes only
    """
    valid = []
    for code in codes:
        if isinstance(code, str) and is_valid_hpo_code(code):
            valid.append(code.strip().upper())
        elif isinstance(code, dict):
            # Handle dict format like {"code": "HP:0001234"}
            hpo = code.get("code") or code.get("hpo_id")
            if hpo and is_valid_hpo_code(hpo):
                valid.append(hpo.strip().upper())
    return valid


def sanitize_gene_symbols(symbols: list[Any]) -> list[str]:
    """
    Filter and sanitize a list of gene symbols.

    Args:
        symbols: List of potential gene symbols

    Returns:
        List of valid gene symbols only
    """
    valid = []
    for symbol in symbols:
        if isinstance(symbol, str) and is_valid_gene_symbol(symbol):
            valid.append(symbol.strip().upper())
        elif isinstance(symbol, dict):
            # Handle dict format
            gene = symbol.get("gene_symbol") or symbol.get("code") or symbol.get("gene")
            if gene and is_valid_gene_symbol(gene):
                valid.append(gene.strip().upper())
    return valid


def validate_phenotype_input(phenotypes: list[Any]) -> tuple[list[str], list[str]]:
    """
    Validate and separate phenotype inputs into codes and text descriptions.

    Args:
        phenotypes: Mixed list of HPO codes and text descriptions

    Returns:
        Tuple of (valid_hpo_codes, text_descriptions)
    """
    hpo_codes = []
    text_descriptions = []

    for p in phenotypes:
        if isinstance(p, str):
            p = p.strip()
            if is_valid_hpo_code(p):
                hpo_codes.append(p.upper())
            elif len(p) > 2:  # Minimum length for a description
                text_descriptions.append(p)
        elif isinstance(p, dict):
            code = p.get("code") or p.get("hpo_id")
            value = p.get("value") or p.get("name")

            if code and is_valid_hpo_code(code):
                hpo_codes.append(code.strip().upper())
            elif value and len(value.strip()) > 2:
                text_descriptions.append(value.strip())

    return hpo_codes, text_descriptions


def validate_genetic_input(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Validate genetic variant input.

    Args:
        variants: List of variant dictionaries

    Returns:
        List of validated variant dictionaries
    """
    valid = []

    for v in variants:
        if not isinstance(v, dict):
            continue

        gene = v.get("gene_symbol") or v.get("code") or v.get("gene")

        # Gene symbol is required and must be valid
        if not gene or not is_valid_gene_symbol(gene):
            logger.warning("invalid_gene_symbol", input=gene)
            continue

        validated = {
            "gene_symbol": gene.strip().upper(),
            "notation": v.get("notation") or v.get("value") or "",
            "pathogenicity": v.get("pathogenicity") or v.get("severity") or "unknown",
            "zygosity": v.get("zygosity") or "unknown",
        }

        valid.append(validated)

    return valid


class InputValidator:
    """
    Validator class for clinical inputs with caching and statistics.
    """

    def __init__(self) -> None:
        self._validation_stats = {
            "hpo_valid": 0,
            "hpo_invalid": 0,
            "gene_valid": 0,
            "gene_invalid": 0,
        }

    def validate_hpo_code(self, code: str | None) -> bool:
        """Validate HPO code and track statistics."""
        valid = is_valid_hpo_code(code)
        if valid:
            self._validation_stats["hpo_valid"] += 1
        else:
            self._validation_stats["hpo_invalid"] += 1
        return valid

    def validate_gene_symbol(self, symbol: str | None) -> bool:
        """Validate gene symbol and track statistics."""
        valid = is_valid_gene_symbol(symbol)
        if valid:
            self._validation_stats["gene_valid"] += 1
        else:
            self._validation_stats["gene_invalid"] += 1
        return valid

    def get_stats(self) -> dict[str, int]:
        """Get validation statistics."""
        return dict(self._validation_stats)

    def reset_stats(self) -> None:
        """Reset validation statistics."""
        for key in self._validation_stats:
            self._validation_stats[key] = 0
