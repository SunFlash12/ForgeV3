"""
Tests for diagnosis input validation module.

Tests HPO code validation, gene symbol validation, and input sanitization.
"""

from forge.services.diagnosis.validation import (
    InputValidator,
    is_valid_disease_id,
    is_valid_gene_symbol,
    is_valid_hpo_code,
    sanitize_gene_symbols,
    sanitize_hpo_codes,
    validate_genetic_input,
    validate_phenotype_input,
)


class TestHPOValidation:
    """Tests for HPO code validation."""

    def test_valid_hpo_codes(self):
        """Test that valid HPO codes are accepted."""
        valid_codes = [
            "HP:0000001",
            "HP:0001234",
            "HP:9999999",
            "hp:0001234",  # lowercase should work
            " HP:0001234 ",  # with whitespace
        ]
        for code in valid_codes:
            assert is_valid_hpo_code(code), f"Should accept {code}"

    def test_invalid_hpo_codes(self):
        """Test that invalid HPO codes are rejected."""
        invalid_codes = [
            "",
            None,
            "HP:123",  # too short
            "HP:12345678",  # too long
            "HPO:0001234",  # wrong prefix
            "HP0001234",  # missing colon
            "HP:000123A",  # contains letter
            "MONDO:0001234",  # wrong ontology
            "random text",
            123,  # not a string
        ]
        for code in invalid_codes:
            assert not is_valid_hpo_code(code), f"Should reject {code}"


class TestGeneSymbolValidation:
    """Tests for gene symbol validation."""

    def test_valid_gene_symbols(self):
        """Test that valid gene symbols are accepted."""
        valid_symbols = [
            "BRCA1",
            "BRCA2",
            "TP53",
            "HLA-DRB1",
            "CFTR",
            "brca1",  # lowercase
            " BRCA1 ",  # with whitespace
        ]
        for symbol in valid_symbols:
            assert is_valid_gene_symbol(symbol), f"Should accept {symbol}"

    def test_invalid_gene_symbols(self):
        """Test that invalid gene symbols are rejected."""
        invalid_symbols = [
            "",
            None,
            "A",  # too short
            "VERYLONGGENENAMETHATEXCEEDSLIMIT",  # too long
            "123ABC",  # starts with number
            "GENE WITH SPACE",  # contains space
            "GENE@SYMBOL",  # invalid character
            123,  # not a string
        ]
        for symbol in invalid_symbols:
            assert not is_valid_gene_symbol(symbol), f"Should reject {symbol}"


class TestDiseaseIDValidation:
    """Tests for disease ID validation."""

    def test_valid_mondo_ids(self):
        """Test that valid MONDO IDs are accepted."""
        valid_ids = [
            "MONDO:0000001",
            "MONDO:1234567",
        ]
        for disease_id in valid_ids:
            assert is_valid_disease_id(disease_id), f"Should accept {disease_id}"

    def test_valid_omim_ids(self):
        """Test that valid OMIM IDs are accepted."""
        valid_ids = [
            "123456",
            "654321",
        ]
        for disease_id in valid_ids:
            assert is_valid_disease_id(disease_id), f"Should accept {disease_id}"

    def test_invalid_disease_ids(self):
        """Test that invalid disease IDs are rejected."""
        invalid_ids = [
            "",
            None,
            "MONDO:123",  # too short
            "12345",  # OMIM too short
            "OMIM:123456",  # OMIM shouldn't have prefix in this format
            "random",
        ]
        for disease_id in invalid_ids:
            assert not is_valid_disease_id(disease_id), f"Should reject {disease_id}"


class TestSanitizeHPOCodes:
    """Tests for HPO code sanitization."""

    def test_sanitize_valid_codes(self):
        """Test sanitization of valid codes."""
        codes = ["HP:0001234", "hp:0005678", " HP:0009999 "]
        result = sanitize_hpo_codes(codes)
        assert result == ["HP:0001234", "HP:0005678", "HP:0009999"]

    def test_sanitize_filters_invalid(self):
        """Test that invalid codes are filtered out."""
        codes = ["HP:0001234", "invalid", "HP:123", "HP:0005678"]
        result = sanitize_hpo_codes(codes)
        assert result == ["HP:0001234", "HP:0005678"]

    def test_sanitize_dict_format(self):
        """Test sanitization of dict format input."""
        codes = [
            {"code": "HP:0001234"},
            {"hpo_id": "HP:0005678"},
            {"code": "invalid"},
        ]
        result = sanitize_hpo_codes(codes)
        assert result == ["HP:0001234", "HP:0005678"]

    def test_sanitize_empty_list(self):
        """Test sanitization of empty list."""
        assert sanitize_hpo_codes([]) == []


class TestSanitizeGeneSymbols:
    """Tests for gene symbol sanitization."""

    def test_sanitize_valid_symbols(self):
        """Test sanitization of valid symbols."""
        symbols = ["BRCA1", "tp53", " CFTR "]
        result = sanitize_gene_symbols(symbols)
        assert result == ["BRCA1", "TP53", "CFTR"]

    def test_sanitize_filters_invalid(self):
        """Test that invalid symbols are filtered out."""
        symbols = ["BRCA1", "123", "A", "TP53"]
        result = sanitize_gene_symbols(symbols)
        assert result == ["BRCA1", "TP53"]

    def test_sanitize_dict_format(self):
        """Test sanitization of dict format input."""
        symbols = [
            {"gene_symbol": "BRCA1"},
            {"code": "TP53"},
            {"gene": "CFTR"},
        ]
        result = sanitize_gene_symbols(symbols)
        assert result == ["BRCA1", "TP53", "CFTR"]


class TestValidatePhenotypeInput:
    """Tests for phenotype input validation."""

    def test_separates_codes_and_text(self):
        """Test that HPO codes and text descriptions are separated."""
        phenotypes = [
            "HP:0001234",
            "seizures",
            "HP:0005678",
            "developmental delay",
        ]
        codes, text = validate_phenotype_input(phenotypes)
        assert codes == ["HP:0001234", "HP:0005678"]
        assert text == ["seizures", "developmental delay"]

    def test_handles_dict_input(self):
        """Test handling of dict format input."""
        phenotypes = [
            {"code": "HP:0001234", "value": "Seizures"},
            {"value": "hypotonia"},
        ]
        codes, text = validate_phenotype_input(phenotypes)
        assert codes == ["HP:0001234"]
        assert text == ["hypotonia"]

    def test_filters_short_text(self):
        """Test that very short text is filtered."""
        phenotypes = ["HP:0001234", "a", "ab", "abc"]
        codes, text = validate_phenotype_input(phenotypes)
        assert codes == ["HP:0001234"]
        assert text == ["abc"]  # Only 3+ chars


class TestValidateGeneticInput:
    """Tests for genetic variant input validation."""

    def test_validates_gene_symbols(self):
        """Test that gene symbols are validated."""
        variants = [
            {"gene_symbol": "BRCA1", "notation": "c.123A>G"},
            {"gene_symbol": "123", "notation": "invalid"},
            {"gene_symbol": "TP53", "pathogenicity": "pathogenic"},
        ]
        result = validate_genetic_input(variants)
        assert len(result) == 2
        assert result[0]["gene_symbol"] == "BRCA1"
        assert result[1]["gene_symbol"] == "TP53"

    def test_normalizes_output(self):
        """Test that output is normalized."""
        variants = [
            {
                "gene_symbol": "brca1",
                "notation": "c.123A>G",
                "pathogenicity": "Pathogenic",
                "zygosity": "heterozygous",
            }
        ]
        result = validate_genetic_input(variants)
        assert len(result) == 1
        assert result[0]["gene_symbol"] == "BRCA1"  # uppercase
        assert result[0]["notation"] == "c.123A>G"
        assert result[0]["pathogenicity"] == "Pathogenic"
        assert result[0]["zygosity"] == "heterozygous"

    def test_handles_missing_fields(self):
        """Test handling of missing optional fields."""
        variants = [{"gene_symbol": "BRCA1"}]
        result = validate_genetic_input(variants)
        assert len(result) == 1
        assert result[0]["gene_symbol"] == "BRCA1"
        assert result[0]["notation"] == ""
        assert result[0]["pathogenicity"] == "unknown"
        assert result[0]["zygosity"] == "unknown"


class TestInputValidator:
    """Tests for InputValidator class."""

    def test_tracks_statistics(self):
        """Test that validation statistics are tracked."""
        validator = InputValidator()

        # Validate some codes
        validator.validate_hpo_code("HP:0001234")
        validator.validate_hpo_code("invalid")
        validator.validate_hpo_code("HP:0005678")

        validator.validate_gene_symbol("BRCA1")
        validator.validate_gene_symbol("123")

        stats = validator.get_stats()
        assert stats["hpo_valid"] == 2
        assert stats["hpo_invalid"] == 1
        assert stats["gene_valid"] == 1
        assert stats["gene_invalid"] == 1

    def test_reset_statistics(self):
        """Test that statistics can be reset."""
        validator = InputValidator()
        validator.validate_hpo_code("HP:0001234")
        validator.reset_stats()

        stats = validator.get_stats()
        assert stats["hpo_valid"] == 0
        assert stats["hpo_invalid"] == 0


class TestSecurityCases:
    """Tests for security-related edge cases."""

    def test_injection_attempt_hpo(self):
        """Test that injection attempts in HPO codes are rejected."""
        malicious = [
            "HP:0001234; DROP TABLE users;",
            "HP:0001234<script>alert(1)</script>",
            "HP:0001234\n\rHTTP/1.1 200 OK",
            "HP:0001234' OR '1'='1",
        ]
        for code in malicious:
            assert not is_valid_hpo_code(code), f"Should reject injection: {code}"

    def test_injection_attempt_gene(self):
        """Test that injection attempts in gene symbols are rejected."""
        malicious = [
            "BRCA1; DROP TABLE",
            "BRCA1<script>",
            "BRCA1\x00NULL",
        ]
        for symbol in malicious:
            assert not is_valid_gene_symbol(symbol), f"Should reject injection: {symbol}"

    def test_unicode_normalization(self):
        """Test handling of unicode characters."""
        # These should be rejected as they contain non-ASCII
        unicode_codes = [
            "HP:０００１２３４",  # fullwidth digits
            "ＨＰ:0001234",  # fullwidth letters
        ]
        for code in unicode_codes:
            assert not is_valid_hpo_code(code), f"Should reject unicode: {code}"
