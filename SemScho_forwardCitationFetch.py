import requests
import pandas as pd
import time
from typing import List, Dict, Optional
import json

class SemanticScholarCitationScraper:
    def __init__(self, api_key: Optional[str] = None):
        
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.headers = {
            'User-Agent': 'SemanticScholarCitationScraper/1.0'
        }
        
        if api_key:
            self.headers["x-api-key"] = api_key  

        self.delay = 3.1 if not api_key else 0.31 
        self.has_api_key = api_key is not None
    
    def get_paper_by_doi(self, doi: str) -> Optional[Dict]:

        clean_doi = doi.replace('DOI:', '').replace('doi:', '').strip()
        
        url = f"{self.base_url}/paper/DOI:{clean_doi}"
        params = {
            'fields': 'paperId,corpusId,title,authors,year,citationCount,venue,externalIds'
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 200:
                paper_data = response.json()
                print(f"✓ Found paper: {paper_data.get('title', 'Unknown')[:60]}...")
                return paper_data
            elif response.status_code == 404:
                print(f"✗ Paper not found in S2AG for DOI: {clean_doi}")
                return None
            elif response.status_code == 429:
                print("Rate limit hit, waiting longer...")
                time.sleep(60)  
                return self.get_paper_by_doi(doi)  
            else:
                print(f"✗ API error for DOI {clean_doi}: HTTP {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"✗ Timeout for DOI: {clean_doi}")
            return None
        except Exception as e:
            print(f"✗ Exception for DOI {clean_doi}: {e}")
            return None
    
    def get_forward_citations(self, paper_id: str, limit: int = 1000) -> List[Dict]:
        url = f"{self.base_url}/paper/{paper_id}/citations"
        params = {
            'fields': 'title,authors,year,venue,citationCount,externalIds,abstract,publicationTypes',
            'limit': min(limit, 1000)  
        }
        
        all_citations = []
        offset = 0
        
        print(f"  Retrieving forward citations...")
        
        while True:
            params['offset'] = offset
            
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    citations = data.get('data', [])
                    
                    if not citations:
                        break
                    
                    all_citations.extend(citations)
                    print(f"    → {len(all_citations)} citations retrieved so far...")
                    
 
                    if len(citations) < 1000:
                        break
                    
                    offset += 1000
                    time.sleep(self.delay)  
                    
                elif response.status_code == 429:
                    print("    Rate limit hit, waiting...")
                    time.sleep(60)
                    continue 
                    
                else:
                    print(f"  ✗ Error getting citations: HTTP {response.status_code}")
                    break
                    
            except requests.exceptions.Timeout:
                print(f"  ✗ Timeout getting citations, stopping...")
                break
            except Exception as e:
                print(f"  ✗ Exception getting citations: {e}")
                break
            
            time.sleep(self.delay) 
        
        return all_citations
    
    def process_dois(self, dois: List[str]) -> pd.DataFrame:
        all_forward_citations = []
        
        for i, doi in enumerate(dois):
            print(f"Processing DOI {i+1}/{len(dois)}: {doi}")
            
            # Get the original paper
            paper = self.get_paper_by_doi(doi)
            if not paper:
                continue
            
            paper_id = paper['paperId']
            original_title = paper.get('title', 'Unknown')
            
            citations = self.get_forward_citations(paper_id)
            print(f"Found {len(citations)} forward citations for: {original_title}")
            
            for citation in citations:
                citing_paper = citation.get('citingPaper', {})
                
                authors = citing_paper.get('authors', [])
                author_names = [author.get('name', '') for author in authors]
                
                external_ids = citing_paper.get('externalIds') or {}
                citing_doi = external_ids.get('DOI', '')
                pubmed_id = external_ids.get('PubMed', '')
                
                citation_data = {
                    'original_doi': doi,
                    'original_title': original_title,
                    'original_paper_id': paper_id,
                    'original_corpus_id': paper.get('corpusId', ''),
                    'citing_title': citing_paper.get('title', ''),
                    'citing_authors': '; '.join(author_names),
                    'citing_year': citing_paper.get('year', ''),
                    'citing_venue': citing_paper.get('venue', ''),
                    'citing_doi': citing_doi,
                    'citing_pubmed_id': pubmed_id,
                    'citing_arxiv_id': external_ids.get('ArXiv', ''),
                    'citing_citation_count': citing_paper.get('citationCount', 0),
                    'citing_paper_id': citing_paper.get('paperId', ''),
                    'citing_publication_types': '; '.join(citing_paper.get('publicationTypes') or []),
                    'citing_abstract': citing_paper.get('abstract', '')[:500] + '...' if citing_paper.get('abstract') else ''
                }
                
                all_forward_citations.append(citation_data)
            
            time.sleep(self.delay)
        
        return pd.DataFrame(all_forward_citations)

def main():

# add dois
    dois = [
"10.3390/nu16152432",
"10.1073/pnas.2317686121",
"10.1038/s43016-024-00961-8",
    ]
    
    api_key = None 
    scraper = SemanticScholarCitationScraper(api_key=api_key)
    
    print(f" Starting forward citation retrieval for {len(dois)} papers...")
    print(f"   Using API key: {'Yes' if api_key else 'No (consider getting one for faster processing)'}")
    print("   S2AG API Documentation: https://api.semanticscholar.org/")
    print()
    
    results_df = scraper.process_dois(dois)
    
    if results_df.empty:
        print(" No citations found. Check your DOIs or try different papers.")
        return
    
    # write to csv
    output_file = "semantic_scholar_forward_citations.csv"
    results_df.to_csv(output_file, index=False, encoding='utf-8')
    print(f" Results saved to {output_file}")
    print(f" Total forward citations found: {len(results_df)}")
    
    print("\n Summary by original paper:")
    summary = results_df.groupby(['original_doi', 'original_title']).agg({
        'citing_title': 'count',
        'citing_year': 'min'
    }).rename(columns={'citing_title': 'citation_count', 'citing_year': 'earliest_citation'}).reset_index()
    
    for _, row in summary.iterrows():
        title = row['original_title'][:50] + "..." if len(row['original_title']) > 50 else row['original_title']
        print(f"   • {title}: {row['citation_count']} citations (earliest: {row['earliest_citation']})")

if __name__ == "__main__":

    main()
