import pandas as pd
from scipy.stats import spearmanr

# Carregar o dataset
try:
    df = pd.read_csv('dataset_code_review.csv')
    print("Dataset carregado com sucesso!")
except FileNotFoundError:
    print("Erro: Arquivo 'dataset_code_review.csv' não encontrado.")
    print("Por favor, certifique-se de que este script e o arquivo CSV estão na mesma pasta.")
    exit()

# Função auxiliar para uma impressão mais clara
def analyze_and_print_correlation(metric, target, dataframe):
    """Calcula e imprime a correlação de Spearman de forma clara."""
    correlation, p_value = spearmanr(dataframe[metric], dataframe[target])
    
    # Define o texto de significância
    significance_text = "Sim" if p_value < 0.05 else "Não"
    
    print(f"\n  Métrica: '{metric}' vs. '{target}'")
    print(f"  Coeficiente de Correlação (rho): {correlation:.4f}")
    print(f"  P-valor: {p_value:.4f}")
    print(f"  É estatisticamente significante? {significance_text} (p-valor {'<' if p_value < 0.05 else '>= GITHUB_TOKEN=ghp_mZ1hJ8vY4cW5xW2nS3K6fG7D9F0A1bI3U4p'}")
    
# --- Análises para cada RQ ---

print("\n--- Análise de Correlação para RQ05: Tamanho ---")
target_variable = 'num_reviews'
for metric in ['size_files_changed', 'size_lines_added', 'size_lines_removed']:
    analyze_and_print_correlation(metric, target_variable, df)

print("\n--- Análise de Correlação para RQ06: Tempo de Análise ---")
analyze_and_print_correlation('analysis_time_hours', target_variable, df)

print("\n--- Análise de Correlação para RQ07: Descrição ---")
analyze_and_print_correlation('description_chars', target_variable, df)

print("\n--- Análise de Correlação para RQ08: Interações ---")
for metric in ['interaction_comments', 'interaction_participants']:
    analyze_and_print_correlation(metric, target_variable, df)