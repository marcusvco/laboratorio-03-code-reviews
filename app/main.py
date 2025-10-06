import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timezone
from tqdm import tqdm

load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")
if not TOKEN:
    raise Exception("Token do GitHub não encontrado. Verifique seu arquivo .env")

HEADERS = {"Authorization": f"Bearer {TOKEN}"}
API_URL = "https://api.github.com/graphql"
TOTAL_REPOSITORIOS = 1

# Query da Fase 1: Leve, apenas para filtrar
PR_FILTER_QUERY = """
query($owner: String!, $name: String!, $prFirst: Int!, $prAfter: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: $prFirst, after: $prAfter, states: [MERGED, CLOSED], orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage, endCursor }
      nodes {
        number
        createdAt
        closedAt
        mergedAt
        reviews(first: 1) { totalCount }
      }
    }
  }
}
"""

# Query da Fase 2: Pede detalhes completos para UM PR específico
PR_DETAIL_QUERY = """
query($owner: String!, $name: String!, $prNumber: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $prNumber) {
      url
      state
      changedFiles
      additions
      deletions
      body
      participants(first: 1) { totalCount }
      comments(first: 1) { totalCount }
    }
  }
}
"""

# A query de repositórios continua a mesma
REPO_QUERY = """
query($queryString: String!, $first: Int!, $after: String) {
  search(query: $queryString, type: REPOSITORY, first: $first, after: $after) {
    repositoryCount
    pageInfo { hasNextPage, endCursor }
    edges {
      node {
        ... on Repository {
          name
          owner { login }
          pullRequests(states: [MERGED, CLOSED]) { totalCount }
        }
      }
    }
  }
}
"""

def fetch_popular_repos():
    # Esta função não precisa de mudanças
    query_string = "stars:>1 sort:stars-desc"
    after_cursor = None
    all_repos = []
    print(f"Buscando os {TOTAL_REPOSITORIOS} repositórios mais populares...")
    while len(all_repos) < TOTAL_REPOSITORIOS:
        variables = { "queryString": query_string, "first": 50, "after": after_cursor }
        response = requests.post(API_URL, json={"query": REPO_QUERY, "variables": variables}, headers=HEADERS)
        if response.status_code != 200: raise Exception(f"Falha na busca de repositórios: {response.status_code}, {response.text}")
        result = response.json()
        edges = result["data"]["search"]["edges"]
        all_repos.extend([edge["node"] for edge in edges])
        page_info = result["data"]["search"]["pageInfo"]
        if page_info["hasNextPage"]: after_cursor = page_info["endCursor"]
        else: break
    return all_repos[:TOTAL_REPOSITORIOS]


def fetch_valid_prs_for_repo(owner, name):
    # --- FASE 1: VARREDURA E FILTRAGEM ---
    pre_filtered_prs = []
    after_cursor = None
    PAGES_TO_FETCH = 5 # Busca os 500 PRs mais recentes para filtrar

    for _ in range(PAGES_TO_FETCH):
        variables = { "owner": owner, "name": name, "prFirst": 100, "prAfter": after_cursor }
        try:
            response = requests.post(API_URL, json={"query": PR_FILTER_QUERY, "variables": variables}, headers=HEADERS, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"  -> Erro na Fase 1 para {owner}/{name}: {e}. Pulando repositório.")
            return []

        result = response.json()
        if "errors" in result:
            print(f"  -> Erro da API na Fase 1 para {owner}/{name}: {result['errors'][0]['message']}. Pulando.")
            return []
        if "data" not in result or not result.get("data") or not result["data"].get("repository"): break
            
        prs_data = result["data"]["repository"]["pullRequests"]
        pre_filtered_prs.extend(prs_data["nodes"])
        if prs_data["pageInfo"]["hasNextPage"]: after_cursor = prs_data["pageInfo"]["endCursor"]
        else: break
            
    # Aplica os filtros do laboratório em memória
    valid_pr_candidates = []
    for pr in pre_filtered_prs:
        if pr["reviews"]["totalCount"] == 0: continue
        created_at = datetime.fromisoformat(pr["createdAt"].replace("Z", "+00:00"))
        closed_or_merged_at_str = pr.get("mergedAt") or pr.get("closedAt")
        if not closed_or_merged_at_str: continue
        closed_or_merged_at = datetime.fromisoformat(closed_or_merged_at_str.replace("Z", "+00:00"))
        analysis_duration = closed_or_merged_at - created_at
        if analysis_duration.total_seconds() / 3600 <= 1: continue
        valid_pr_candidates.append({ "number": pr["number"], "base_data": pr })

    # --- FASE 2: COLETA DE DETALHES ---
    final_prs = []
    if not valid_pr_candidates: return [] # Se nenhum PR passou no filtro, termina aqui

    # Itera apenas nos PRs que passaram no filtro
    for candidate in valid_pr_candidates:
        pr_number = candidate["number"]
        variables = { "owner": owner, "name": name, "prNumber": pr_number }
        try:
            response = requests.post(API_URL, json={"query": PR_DETAIL_QUERY, "variables": variables}, headers=HEADERS, timeout=20)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            # Pula apenas este PR se a busca detalhada falhar
            continue 

        result = response.json()
        if "data" not in result or not result.get("data") or not result["data"].get("repository"): continue

        details = result["data"]["repository"]["pullRequest"]
        base_info = candidate["base_data"]

        # Combina os dados da Fase 1 e Fase 2
        final_prs.append({
            "repo_owner": owner, "repo_name": name, "pr_number": pr_number, "pr_url": details["url"],
            "pr_status": "MERGED" if details["state"] == "MERGED" else "CLOSED",
            "analysis_time_hours": round((datetime.fromisoformat(base_info["closedAt"].replace("Z", "+00:00")) - datetime.fromisoformat(base_info["createdAt"].replace("Z", "+00:00"))).total_seconds() / 3600, 2),
            "size_files_changed": details["changedFiles"], "size_lines_added": details["additions"], "size_lines_removed": details["deletions"],
            "description_chars": len(details["body"]) if details["body"] else 0,
            "interaction_participants": details["participants"]["totalCount"], "interaction_comments": details["comments"]["totalCount"],
            "num_reviews": base_info["reviews"]["totalCount"]
        })
        time.sleep(0.5) # Pequena pausa entre cada PR detalhado para ser gentil com a API

    return final_prs


def main():
    # Esta função não precisa de mudanças, apenas o tempo de espera foi ajustado
    repos = fetch_popular_repos()
    valid_repos = [r for r in repos if r["pullRequests"]["totalCount"] >= 100]
    print(f"\nEncontrados {len(valid_repos)} repositórios válidos para processar. Iniciando coleta sequencial...")
    all_valid_prs = []
    for repo in tqdm(valid_repos, desc="Processando Repositórios"):
        repo_prs = fetch_valid_prs_for_repo(repo["owner"]["login"], repo["name"])
        if repo_prs:
            all_valid_prs.extend(repo_prs)
        time.sleep(1) # Pausa entre cada REPOSITÓRIO

    if not all_valid_prs:
        print("\nNenhum Pull Request válido foi encontrado com os filtros aplicados.")
        return

    df = pd.DataFrame(all_valid_prs)
    df.to_csv("dataset_code_review.csv", index=False)
    print(f"\nProcesso finalizado! O dataset foi salvo em 'dataset_code_review.csv' com {len(df)} registros.")


if __name__ == "__main__":
    main()