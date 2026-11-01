"""Synthetic real-model retrieval benchmark. Never substitutes deterministic vectors."""
import argparse
import asyncio
import hashlib
import io
import json
import platform
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


def make_pdf(pages):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    for content in pages:
        page = writer.add_blank_page(width=595,height=842)
        font = DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        commands=['BT /F1 11 Tf 30 760 Td']
        for line in textwrap.wrap(content,80):
            escaped=line.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
            commands.append('('+escaped+') Tj 0 -20 Td')
        commands.append('ET')
        stream=DecodedStreamObject();stream.set_data('\n'.join(commands).encode('ascii'))
        page[NameObject('/Contents')]=writer._add_object(stream)
    output=io.BytesIO();writer.write(output);return output.getvalue()


def memory():
    if platform.system() != 'Linux': return {'status':'UNMEASURED: use native working-set monitoring'}
    import resource
    return {'python_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            'largest_finished_child_peak_rss_bytes':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024,
            'note':'Lifetime high-water RSS. Child peak is max, not sum, and can include PDF extraction. Not combined system/model memory.'}


async def benchmark(mode, dataset):
    from alembic import command
    from alembic.config import Config
    from app.core.config import Settings
    from app.db.session import create_database
    from app.schemas.extraction import DocumentMetadata, ExtractionFile, initial_revision_id
    from app.services.documents import extract_document, store_document, retrieve
    from app.services.embeddings import LocalEmbeddingProvider, EmbeddingError
    from app.services.hybrid_retrieval import HybridRetrieval
    from sqlalchemy import text
    report={'mode':mode,'platform':platform.platform(),'real_semantic_quality':'UNVERIFIED','queries':[]}
    with tempfile.TemporaryDirectory(prefix='maritime-retrieval-') as directory:
        directory=Path(directory);data=make_pdf(dataset['pages']);source=directory/'synthetic.pdf';source.write_bytes(data)
        settings=Settings(database_url=f"sqlite:///{directory/'benchmark.db'}")
        engine,_=create_database(settings.database_url)
        config=Config(str(ROOT/'backend/alembic.ini'));config.set_main_option('script_location',str(ROOT/'backend/migrations'))
        with engine.begin() as connection:
            config.attributes['connection']=connection;command.upgrade(config,'head')
        provider=LocalEmbeddingProvider(settings);service=HybridRetrieval(engine,provider,settings)
        try:
            if mode=='hybrid':
                try:
                    report['embedding_model_id']=await asyncio.to_thread(provider.identity)
                    report['embedding_model_filename']=Path(settings.embedding_model_path).name
                    with Path(settings.embedding_model_path).open('rb') as weights:
                        report['embedding_model_sha256']=hashlib.file_digest(weights,'sha256').hexdigest()
                    version=subprocess.run([settings.llama_server,'--version'],capture_output=True,text=True,check=True)
                    report['runtime_version']=version.stdout+version.stderr
                except (EmbeddingError,OSError,subprocess.SubprocessError) as error:
                    report.update(status='UNVERIFIED: real embedding weights/runtime unavailable',blocker=str(error),metrics=None)
                    return report
            did=uuid4()
            meta=DocumentMetadata(document_id=did,revision_id=initial_revision_id(did),name='synthetic.pdf',
                source_format='pdf',media_type='application/pdf',sha256=hashlib.sha256(data).hexdigest(),size_bytes=len(data))
            extracted=await extract_document(ExtractionFile(path=source,metadata=meta))
            if extracted.status=='failed': raise RuntimeError(extracted.errors)
            store_document(engine,extracted)
            if mode=='hybrid':
                started=time.perf_counter();report['index']=await service.index_document(str(did))
                report['index_latency_seconds']=time.perf_counter()-started
                if report['index']['mode']!='hybrid':
                    report.update(status='UNVERIFIED: indexing incomplete',metrics=None);return report
            for query in dataset['queries']:
                started=time.perf_counter()
                if mode=='fts5': rows=retrieve(engine,str(did),query['question']);info={'mode':'fts5'}
                else: rows,info=await service.search(str(did),query['question'])
                elapsed=(time.perf_counter()-started)*1000
                if mode=='hybrid' and info['mode']!='hybrid':
                    report.update(status='UNVERIFIED: semantic inference fell back to FTS5',metrics=None);return report
                pages=[r['locator']['page_number'] for r in rows]
                relevant=set(query['pages']); hits=set(pages)&relevant
                rank=next((i for i,page in enumerate(pages,1) if page in relevant),None)
                for row in rows:
                    with engine.connect() as connection:
                        unit=connection.execute(text('SELECT revision_id,text,locator FROM content_units WHERE id=:id'),{'id':row['unit_id']}).mappings().one()
                    assert row['document_id']==str(did) and row['revision_id']==str(meta.revision_id)==unit['revision_id']
                    assert row['excerpt'] in unit['text'] and row['locator']==json.loads(unit['locator'])
                report['queries'].append({**query,'retrieved_pages':pages,'latency_ms':elapsed,'source_integrity':True,
                    'recall_at_3':len(hits)/len(relevant) if relevant else None,
                    'mrr_at_3':1/rank if rank else 0 if relevant else None,
                    'unsupported_has_candidates':bool(rows) if not relevant else None})
            metrics={}
            for group in ['all_supported','english','vietnamese','exact_reference','equipment']:
                selected=[q for q in report['queries'] if q['pages'] and (group=='all_supported' or q['group']==group)]
                metrics[group]={'count':len(selected),'recall_at_3':sum(q['recall_at_3'] for q in selected)/len(selected),
                    'mrr_at_3':sum(q['mrr_at_3'] for q in selected)/len(selected)}
            unsupported=[q for q in report['queries'] if not q['pages']]
            latencies=sorted(q['latency_ms'] for q in report['queries'])
            report.update(status='MEASURED',metrics=metrics,unsupported_candidate_rate=sum(q['unsupported_has_candidates'] for q in unsupported)/len(unsupported),
                latency_ms={'mean':sum(latencies)/len(latencies),'p95_nearest_rank':latencies[max(0,__import__('math').ceil(.95*len(latencies))-1)]},
                real_semantic_quality='MEASURED with configured real local provider' if mode=='hybrid' else 'UNVERIFIED: FTS5-only baseline')
        finally:
            await service.close();engine.dispose()
            report['memory']=memory()
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mode',choices=['fts5','hybrid'],required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    dataset=json.loads((ROOT/'benchmarks/hybrid_retrieval_v1.json').read_text(encoding='utf-8'))
    result=asyncio.run(benchmark(args.mode,dataset));args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key!='queries'},indent=2,ensure_ascii=False))
