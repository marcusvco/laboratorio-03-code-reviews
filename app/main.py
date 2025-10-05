import os
import requests

from dotenv import load_dotenv
from datetime import datetime, timezone
from models.repository import Repository
from models.pull_request import PullRequest
from utils.constants import TOTAL_REPOSITORIOS

load_dotenv()

token = os.getenv("GITHUB_TOKEN")
headers = {"Authorization": f"Bearer {token}"}
query = """
query($queryString: String!, $first: Int!, $after: String, $prFirst: Int!) {
  search(query: $queryString, type: REPOSITORY, first: $first, after: $after) {
    repositoryCount
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        ... on Repository {
          name
          owner {
            login
          }
          stargazerCount
          forkCount
          url
          description
          pullRequests(first: $prFirst, states: [CLOSED, MERGED], orderBy: {field: CREATED_AT, direction: DESC}) {
            totalCount
            nodes {
              number
              title
              createdAt
              merged
              closed
              author {
                login
              }
              reviews(first: 5) {
                nodes {
                  author {
                    login
                  }
                  submittedAt
                  state
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


def fetch_github_repos() -> list[Repository]:
    query_string = "stars:>1"
    first = 50
    after_cursor = None
    all_repos = []

    print(f"Buscando {TOTAL_REPOSITORIOS} repositórios mais populares no GitHub...")

    while len(all_repos) < TOTAL_REPOSITORIOS:
        variables = {
            "queryString": query_string,
            "first": first,
            "after": after_cursor,
            "prFirst": 1,
        }
        response = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=headers,
        )

        if response.status_code != 200:
            raise Exception(f"Query failed: {response.status_code}, {response.text}")

        result = response.json()
        edges = result["data"]["search"]["edges"]

        for edge in edges:
            if len(all_repos) >= TOTAL_REPOSITORIOS:
                break

            repo = edge["node"]

            age_years = 0
            created_at_str = repo.get("createdAt")
            if created_at_str:
                created_at_date = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
                age_delta = datetime.now(timezone.utc) - created_at_date
                age_years = age_delta.days / 365.25

            pull_requests = []
            for pr in repo.get("pullRequests", {}).get("nodes", []):
                pull_requests.append(
                    PullRequest(url=f"{repo['url']}/pull/{pr['number']}")
                )

            all_repos.append(
                Repository(
                    name=repo["name"],
                    stars=repo["stargazerCount"],
                    # maturidade_anos=round(age_years, 2),
                    # atividade_releases=repo["releases"]["totalCount"],
                    url=repo["url"],
                    pull_requests=pull_requests,
                )
            )

        page_info = result["data"]["search"]["pageInfo"]

        if page_info["hasNextPage"] and len(all_repos) < TOTAL_REPOSITORIOS:
            after_cursor = page_info["endCursor"]
        else:
            break

    return all_repos[:TOTAL_REPOSITORIOS]


if __name__ == "__main__":
    repositories = fetch_github_repos()
    for repo in repositories:
        print("-----")
        print(repo)
