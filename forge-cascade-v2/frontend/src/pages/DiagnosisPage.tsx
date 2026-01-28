import { useState, useCallback } from 'react';
import {
  Stethoscope,
  Search,
  Plus,
  X,
  ArrowRight,
  AlertCircle,
  CheckCircle,
  Loader2,
  Activity,
  Pill,
  Dna,
  FileText,
  ChevronDown,
  ChevronUp,
  RefreshCw,
} from 'lucide-react';
import { Card, Button, Badge, Modal } from '../components/common';
import { api } from '../api/client';
import axios from 'axios';

interface Phenotype {
  hpo_id: string;
  name: string;
  definition?: string;
}

interface DiagnosisResult {
  disease_id: string;
  disease_name: string;
  confidence: number;
  matching_phenotypes: string[];
  evidence: string[];
}

interface DrugInfo {
  drug_id: string;
  drug_name: string;
  relationship: string;
  evidence_level?: string;
}

interface GeneInfo {
  gene_id: string;
  gene_symbol: string;
  association_type: string;
  evidence?: string;
}

type DiagnosisStep = 'input' | 'processing' | 'results';

export default function DiagnosisPage() {
  // Input state
  const [phenotypeSearch, setPhenotypeSearch] = useState('');
  const [searchResults, setSearchResults] = useState<Phenotype[]>([]);
  const [selectedPhenotypes, setSelectedPhenotypes] = useState<Phenotype[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  // Diagnosis state
  const [step, setStep] = useState<DiagnosisStep>('input');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<DiagnosisResult[]>([]);
  const [recommendations, setRecommendations] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Detail modals
  const [selectedDisease, setSelectedDisease] = useState<DiagnosisResult | null>(null);
  const [drugInfo, setDrugInfo] = useState<DrugInfo[]>([]);
  const [geneInfo, setGeneInfo] = useState<GeneInfo[]>([]);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [expandedResult, setExpandedResult] = useState<string | null>(null);

  // Search for phenotypes
  const searchPhenotypes = useCallback(async (query: string) => {
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    try {
      const response = await api.searchPhenotypes(query);
      setSearchResults(response.phenotypes || []);
    } catch {
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  }, []);

  // Debounced search
  const handleSearchChange = (value: string) => {
    setPhenotypeSearch(value);
    const timeoutId = setTimeout(() => searchPhenotypes(value), 300);
    return () => clearTimeout(timeoutId);
  };

  // Add phenotype to selection
  const addPhenotype = (phenotype: Phenotype) => {
    if (!selectedPhenotypes.find((p) => p.hpo_id === phenotype.hpo_id)) {
      setSelectedPhenotypes([...selectedPhenotypes, phenotype]);
    }
    setPhenotypeSearch('');
    setSearchResults([]);
  };

  // Remove phenotype from selection
  const removePhenotype = (hpoId: string) => {
    setSelectedPhenotypes(selectedPhenotypes.filter((p) => p.hpo_id !== hpoId));
  };

  // Start diagnosis
  const startDiagnosis = async () => {
    if (selectedPhenotypes.length === 0) {
      setError('Please add at least one phenotype or symptom');
      return;
    }

    setError(null);
    setStep('processing');
    setProgress(10);

    try {
      // Create session
      const session = await api.createDiagnosisSession({
        phenotypes: selectedPhenotypes.map((p) => p.hpo_id),
      });
      setSessionId(session.session_id);
      setProgress(30);

      // Start diagnosis
      await api.startDiagnosis(session.session_id, {
        symptoms: selectedPhenotypes.map((p) => p.name),
      });
      setProgress(60);

      // Get results
      const diagnosisResults = await api.getDiagnosisResults(session.session_id);
      setResults(diagnosisResults.diagnoses || []);
      setRecommendations(diagnosisResults.recommendations || []);
      setProgress(100);
      setStep('results');
    } catch (err) {
      let errorMessage = 'Failed to complete diagnosis';
      if (axios.isAxiosError(err) && err.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      }
      setError(errorMessage);
      setStep('input');
    }
  };

  // Load disease details
  const loadDiseaseDetails = async (disease: DiagnosisResult) => {
    setSelectedDisease(disease);
    setLoadingDetails(true);
    setDrugInfo([]);
    setGeneInfo([]);

    try {
      const [drugs, genes] = await Promise.all([
        api.getDrugDiseaseInfo(disease.disease_id).catch(() => ({ drugs: [] })),
        api.getGeneAssociations(disease.disease_id).catch(() => ({ genes: [] })),
      ]);

      setDrugInfo(drugs.drugs || []);
      setGeneInfo(genes.genes || []);
    } catch {
      // Silently handle errors - partial data is acceptable
    } finally {
      setLoadingDetails(false);
    }
  };

  // Reset diagnosis
  const resetDiagnosis = () => {
    setStep('input');
    setSessionId(null);
    setProgress(0);
    setResults([]);
    setRecommendations([]);
    setError(null);
    setSelectedPhenotypes([]);
  };

  // Get confidence color
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-400 bg-green-500/15';
    if (confidence >= 0.6) return 'text-amber-400 bg-amber-500/15';
    if (confidence >= 0.4) return 'text-orange-400 bg-orange-500/15';
    return 'text-red-400 bg-red-500/15';
  };

  return (
    <div className="px-3 sm:px-4 lg:px-6 py-4 sm:py-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-violet-500/15 rounded-lg">
            <Stethoscope className="w-6 h-6 text-violet-400" />
          </div>
          <h1 className="text-2xl font-bold text-slate-100">Differential Diagnosis</h1>
        </div>
        <p className="text-slate-400">
          AI-powered diagnostic analysis using the PrimeKG biomedical knowledge graph
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-6 p-4 bg-red-500/10 border border-white/10 rounded-lg flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <span className="text-red-400">{error}</span>
          <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Step: Input */}
      {step === 'input' && (
        <div className="space-y-6">
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-slate-100 mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-violet-500" />
              Enter Symptoms & Phenotypes
            </h2>

            {/* Phenotype Search */}
            <div className="relative mb-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />

                <input
                  type="text"
                  value={phenotypeSearch}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  className="input pl-10"
                  placeholder="Search for symptoms (e.g., headache, fatigue, fever)..."
                />
                {isSearching && (
                  <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 animate-spin" />
                )}
              </div>

              {/* Search Results Dropdown */}
              {searchResults.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-surface-800 border border-white/10 rounded-lg shadow-lg max-h-64 overflow-y-auto">
                  {searchResults.map((phenotype) => (
                    <button
                      key={phenotype.hpo_id}
                      onClick={() => addPhenotype(phenotype)}
                      className="w-full px-4 py-3 text-left hover:bg-white/5 border-b border-white/10 last:border-0"
                    >
                      <div className="font-medium text-slate-100">{phenotype.name}</div>
                      <div className="text-xs text-slate-400">{phenotype.hpo_id}</div>
                      {phenotype.definition && (
                        <div className="text-sm text-slate-400 mt-1 line-clamp-2">
                          {phenotype.definition}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Selected Phenotypes */}
            <div className="mb-6">
              <label className="label">Selected Symptoms ({selectedPhenotypes.length})</label>
              {selectedPhenotypes.length === 0 ? (
                <div className="p-8 text-center bg-white/5 rounded-lg border-2 border-dashed border-white/10">
                  <Activity className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                  <p className="text-slate-400">Search and add symptoms above</p>
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {selectedPhenotypes.map((phenotype) => (
                    <div
                      key={phenotype.hpo_id}
                      className="flex items-center gap-2 px-3 py-2 bg-violet-500/15 text-violet-400 rounded-lg"
                    >
                      <span className="text-sm font-medium">{phenotype.name}</span>
                      <button
                        onClick={() => removePhenotype(phenotype.hpo_id)}
                        className="p-0.5 hover:bg-violet-500/20 rounded"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Quick Add Common Symptoms */}
            <div className="mb-6">
              <label className="label">Quick Add Common Symptoms</label>
              <div className="flex flex-wrap gap-2">
                {[
                  { hpo_id: 'HP:0002315', name: 'Headache' },
                  { hpo_id: 'HP:0001945', name: 'Fever' },
                  { hpo_id: 'HP:0012378', name: 'Fatigue' },
                  { hpo_id: 'HP:0002018', name: 'Nausea' },
                  { hpo_id: 'HP:0002014', name: 'Diarrhea' },
                  { hpo_id: 'HP:0012531', name: 'Pain' },
                  { hpo_id: 'HP:0000969', name: 'Edema' },
                  { hpo_id: 'HP:0002094', name: 'Dyspnea' },
                ].map((symptom) => (
                  <button
                    key={symptom.hpo_id}
                    onClick={() => addPhenotype(symptom)}
                    disabled={selectedPhenotypes.some((p) => p.hpo_id === symptom.hpo_id)}
                    className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                      selectedPhenotypes.some((p) => p.hpo_id === symptom.hpo_id)
                        ? 'bg-white/5 text-slate-400 border-white/10 cursor-not-allowed'
                        : 'bg-white/5 text-slate-300 border-white/10 hover:border-violet-400 hover:text-violet-400'
                    }`}
                  >
                    <Plus className="w-3 h-3 inline mr-1" />
                    {symptom.name}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex justify-end">
              <Button
                onClick={startDiagnosis}
                disabled={selectedPhenotypes.length === 0}
                icon={<ArrowRight className="w-4 h-4" />}
              >
                Analyze Symptoms
              </Button>
            </div>
          </Card>

          {/* Information Card */}
          <Card className="p-6 bg-gradient-to-br from-violet-500/10 to-indigo-500/10 border-violet-500/30">
            <h3 className="font-semibold text-violet-300 mb-2">About This Tool</h3>
            <p className="text-sm text-violet-300/80 mb-3">
              This differential diagnosis engine uses the PrimeKG biomedical knowledge graph to analyze
              symptoms and phenotypes. It provides potential diagnoses ranked by confidence, along with
              relevant drug and gene associations.
            </p>
            <p className="text-xs text-violet-400">
              This tool is for educational and research purposes only. Always consult a qualified
              healthcare professional for medical advice.
            </p>
          </Card>
        </div>
      )}

      {/* Step: Processing */}
      {step === 'processing' && (
        <Card className="p-12 text-center">
          <Loader2 className="w-16 h-16 text-violet-500 mx-auto mb-6 animate-spin" />
          <h2 className="text-xl font-semibold text-slate-100 mb-2">Analyzing Symptoms</h2>
          <p className="text-slate-400 mb-6">
            Querying the PrimeKG knowledge graph for differential diagnoses...
          </p>

          {/* Progress Bar */}
          <div className="max-w-md mx-auto">
            <div className="h-2 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-violet-500 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="mt-2 text-sm text-slate-400">{progress}% complete</div>
          </div>

          <div className="mt-8 text-sm text-slate-400">
            Session: {sessionId || 'Creating...'}
          </div>
        </Card>
      )}

      {/* Step: Results */}
      {step === 'results' && (
        <div className="space-y-6">
          {/* Results Header */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-100">
                {results.length} Potential Diagnoses Found
              </h2>
              <p className="text-sm text-slate-400">
                Based on {selectedPhenotypes.length} symptoms analyzed
              </p>
            </div>
            <Button variant="secondary" onClick={resetDiagnosis} icon={<RefreshCw className="w-4 h-4" />}>
              New Analysis
            </Button>
          </div>

          {/* Analyzed Symptoms */}
          <Card className="p-4">
            <div className="flex flex-wrap gap-2">
              <span className="text-sm font-medium text-slate-300 mr-2">Analyzed:</span>
              {selectedPhenotypes.map((p) => (
                <Badge key={p.hpo_id} variant="primary">
                  {p.name}
                </Badge>
              ))}
            </div>
          </Card>

          {/* Results List */}
          {results.length === 0 ? (
            <Card className="p-8 text-center">
              <FileText className="w-12 h-12 text-slate-400 mx-auto mb-3" />
              <p className="text-slate-400">No matching diagnoses found for the provided symptoms.</p>
            </Card>
          ) : (
            <div className="space-y-4">
              {results.map((result, index) => (
                <Card
                  key={result.disease_id}
                  className={`p-4 transition-all ${
                    expandedResult === result.disease_id ? 'ring-2 ring-violet-500/40' : ''
                  }`}
                >
                  <div
                    className="flex items-start justify-between cursor-pointer"
                    onClick={() =>
                      setExpandedResult(
                        expandedResult === result.disease_id ? null : result.disease_id
                      )
                    }
                  >
                    <div className="flex items-start gap-4">
                      <div className="flex items-center justify-center w-8 h-8 bg-white/5 rounded-full text-slate-300 font-semibold text-sm">
                        {index + 1}
                      </div>
                      <div>
                        <h3 className="font-semibold text-slate-100">{result.disease_name}</h3>
                        <p className="text-sm text-slate-400">{result.disease_id}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div
                        className={`px-3 py-1 rounded-full text-sm font-medium ${getConfidenceColor(
                          result.confidence
                        )}`}
                      >
                        {(result.confidence * 100).toFixed(0)}% confidence
                      </div>
                      {expandedResult === result.disease_id ? (
                        <ChevronUp className="w-5 h-5 text-slate-400" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-slate-400" />
                      )}
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {expandedResult === result.disease_id && (
                    <div className="mt-4 pt-4 border-t border-white/10">
                      {/* Matching Phenotypes */}
                      {result.matching_phenotypes.length > 0 && (
                        <div className="mb-4">
                          <h4 className="text-sm font-medium text-slate-300 mb-2">
                            Matching Phenotypes
                          </h4>
                          <div className="flex flex-wrap gap-2">
                            {result.matching_phenotypes.map((p, i) => (
                              <Badge key={i} variant="success">
                                <CheckCircle className="w-3 h-3 mr-1" />
                                {p}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Evidence */}
                      {result.evidence.length > 0 && (
                        <div className="mb-4">
                          <h4 className="text-sm font-medium text-slate-300 mb-2">Evidence</h4>
                          <ul className="text-sm text-slate-300 space-y-1">
                            {result.evidence.map((e, i) => (
                              <li key={i} className="flex items-start gap-2">
                                <span className="text-violet-500 mt-1">•</span>
                                {e}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Action Buttons */}
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            loadDiseaseDetails(result);
                          }}
                          icon={<Pill className="w-4 h-4" />}
                        >
                          Drug Info
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            loadDiseaseDetails(result);
                          }}
                          icon={<Dna className="w-4 h-4" />}
                        >
                          Gene Associations
                        </Button>
                      </div>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}

          {/* Recommendations */}
          {recommendations.length > 0 && (
            <Card className="p-6 bg-amber-500/10 border-amber-500/30">
              <h3 className="font-semibold text-amber-300 mb-3 flex items-center gap-2">
                <AlertCircle className="w-5 h-5" />
                Recommendations
              </h3>
              <ul className="space-y-2">
                {recommendations.map((rec, i) => (
                  <li key={i} className="text-sm text-amber-300/80 flex items-start gap-2">
                    <span className="text-amber-500 mt-0.5">•</span>
                    {rec}
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}

      {/* Disease Details Modal */}
      <Modal
        isOpen={selectedDisease !== null}
        onClose={() => setSelectedDisease(null)}
        title={selectedDisease?.disease_name || 'Disease Details'}
        size="lg"
      >
        {loadingDetails ? (
          <div className="py-12 text-center">
            <Loader2 className="w-8 h-8 text-violet-500 mx-auto animate-spin" />
            <p className="text-slate-400 mt-2">Loading details...</p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Drug Information */}
            <div>
              <h3 className="text-lg font-semibold text-slate-100 mb-3 flex items-center gap-2">
                <Pill className="w-5 h-5 text-blue-500" />
                Related Drugs ({drugInfo.length})
              </h3>
              {drugInfo.length === 0 ? (
                <p className="text-slate-400 text-sm">No drug associations found.</p>
              ) : (
                <div className="space-y-2">
                  {drugInfo.map((drug) => (
                    <div
                      key={drug.drug_id}
                      className="p-3 bg-white/5 rounded-lg flex items-center justify-between"
                    >
                      <div>
                        <div className="font-medium text-slate-100">{drug.drug_name}</div>
                        <div className="text-sm text-slate-400">{drug.relationship}</div>
                      </div>
                      {drug.evidence_level && (
                        <Badge variant="secondary">{drug.evidence_level}</Badge>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Gene Associations */}
            <div>
              <h3 className="text-lg font-semibold text-slate-100 mb-3 flex items-center gap-2">
                <Dna className="w-5 h-5 text-green-500" />
                Gene Associations ({geneInfo.length})
              </h3>
              {geneInfo.length === 0 ? (
                <p className="text-slate-400 text-sm">No gene associations found.</p>
              ) : (
                <div className="space-y-2">
                  {geneInfo.map((gene) => (
                    <div
                      key={gene.gene_id}
                      className="p-3 bg-white/5 rounded-lg flex items-center justify-between"
                    >
                      <div>
                        <div className="font-medium text-slate-100">{gene.gene_symbol}</div>
                        <div className="text-sm text-slate-400">{gene.association_type}</div>
                      </div>
                      {gene.evidence && (
                        <span className="text-xs text-slate-400">{gene.evidence}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
