from __future__ import annotations
import argparse, hashlib, json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DELIVERABLES=ROOT/'data/imports/kaoyan_ocr_20260704/deliverables'
OUTPUT=ROOT/'mineru_output'
BOOKS={
 'sensor_core':('传感器短书','sensor_core_chunks.jsonl','kg_candidates_sensor_core.jsonl'),
 'error_theory':('误差理论与数据处理','error_theory_chunks.jsonl','kg_candidates_error_theory.jsonl'),
 'sensor_reference':('传感器长书','sensor_reference_chunks.jsonl','concept_links_sensor.jsonl'),
}
def rows(path):
 return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
def write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(path)
def sid(prefix,value): return prefix+'_'+hashlib.sha1(value.strip().lower().encode()).hexdigest()[:16]
def role(value): return {'text':'reference','formula':'derivation','proof':'derivation'}.get(str(value or 'reference').lower(),str(value or 'reference').lower())
def uniq(values):
 out=[]
 for value in values:
  value=str(value or '').strip()
  if value and value not in out: out.append(value)
 return out
def candidates(source_rows):
 result={}
 for row in source_rows:
  for raw in row.get('concepts',[]):
   name=str(raw.get('concept_name') or '').strip()
   if not name: continue
   item=result.setdefault(name,{'aliases':[],'definition':'','confidence':0,'occ':[],'formulas':[],'prerequisites':[],'related':[]})
   item['aliases']=uniq(item['aliases']+list(raw.get('aliases') or [])); item['definition']=item['definition'] or str(raw.get('definition') or '').strip(); item['confidence']=max(item['confidence'],float(raw.get('confidence') or 0)); item['formulas']+=list(raw.get('formulas') or []); item['prerequisites']=uniq(item['prerequisites']+list(raw.get('prerequisites') or [])); item['related']=uniq(item['related']+list(raw.get('related_concepts') or [])); item['occ'].append((str(row.get('chunk_id') or ''),str(row.get('chapter_title') or ''),role(row.get('semantic_role'))))
 return result
def reference_concepts(link_rows,core):
 result={}
 for link in link_rows:
  name=str(link.get('concept_name') or '').strip()
  if name not in core or float(link.get('confidence') or 0)<.72: continue
  base=core[name]; item=result.setdefault(name,{'aliases':base['aliases'],'definition':base['definition'],'confidence':0,'occ':[],'formulas':[],'prerequisites':base['prerequisites'],'related':base['related']}); item['confidence']=max(item['confidence'],float(link.get('confidence') or 0)); item['occ'].append((str(link.get('reference_chunk_id') or ''),str(link.get('reference_chapter_title') or ''),role(link.get('semantic_role'))))
 return result
def graph(book,concept_map,chunk_rows):
 by_chunk={str(x.get('chunk_id') or ''):x for x in chunk_rows}; name_ids={n:sid('CONCEPT',n) for n in concept_map}; concepts=[]; occurrences=[]; formulas=[]
 for name,item in sorted(concept_map.items()):
  cid=name_ids[name]; own=[]; seen=set()
  for chunk_id,title,r in item['occ']:
   if not chunk_id or (chunk_id,r) in seen: continue
   seen.add((chunk_id,r)); chunk=by_chunk.get(chunk_id,{}); occ={'occurrence_id':sid('OCC',cid+chunk_id+r),'concept_id':cid,'concept_name':name,'context_id':chunk_id,'chunk_id':chunk_id,'page_idx':int(chunk.get('page_idx',-1) or -1),'bbox':[],'role':r,'section_title':title or str(chunk.get('title') or '')}; own.append(occ); occurrences.append(occ)
  concepts.append({'concept_id':cid,'canonical_name':name,'aliases':uniq([name]+item['aliases']),'definition':item['definition'],'source_context':'; '.join(f"[{x['section_title']}] {name} ({x['chunk_id']})" for x in own[:8]),'confidence':round(item['confidence'],3),'occurrence_count':len(own),'occurrences':own,'roles':sorted({x['role'] for x in own})})
  for i,f in enumerate(item['formulas']):
   latex=str(f.get('latex') or f.get('formula') or '').strip() if isinstance(f,dict) else str(f).strip()
   if latex: formulas.append({'formula_id':sid('FORMULA',cid+str(i)+latex),'formula_latex':latex,'variables':[],'source_contexts':[],'related_concepts':[cid]})
 relations=[]; seen=set()
 for name,item in concept_map.items():
  for rel,targets in [('depends_on',item['prerequisites']),('references',item['related'])]:
   for target in targets:
    key=(name,rel,target)
    if target not in name_ids or target==name or key in seen: continue
    seen.add(key); relations.append({'source_concept':name,'source_id':name_ids[name],'relation':rel,'target_concept':target,'target_id':name_ids[target],'evidence_chunk':'','evidence_text':'','page_idx':-1,'section_title':''})
 meta={'source':'external_ocr_jsonl','book_name':book,'generated_at':datetime.now().isoformat(),'total_chunks':len(chunk_rows),'total_contexts':len(chunk_rows),'total_concepts':len(concepts),'total_formulas':len(formulas),'total_occurrences':len(occurrences),'total_relations':len(relations),'relations_resolved':len(relations)}
 return {'meta':meta,'concepts':concepts,'formulas':formulas,'occurrences':occurrences,'relations':relations}
def build(book_id,deliverables,output):
 book,chunk_file,source_file=BOOKS[book_id]; chunk_rows=rows(deliverables/chunk_file)
 if book_id=='sensor_reference': concept_map=reference_concepts(rows(deliverables/source_file),candidates(rows(deliverables/'kg_candidates_sensor_core.jsonl')))
 else: concept_map=candidates(rows(deliverables/source_file))
 data=graph(book,concept_map,chunk_rows); folder=output/book/'hybrid_auto_external'; graph_path=folder/f'{book}_knowledge_graph.json'; middle=[{'chunk_id':str(x.get('chunk_id') or ''),'content':str(x.get('text') or ''),'section_title':str(x.get('title') or ''),'page_idx':int(x.get('page_idx',-1) or -1),'role':role(x.get('semantic_role'))} for x in chunk_rows]; write(graph_path,data); write(folder/f'{book}_middle_chunks.json',middle); mirror=ROOT/'data'/'progress'/book/'hybrid_auto_external'; write(mirror/f'{book}_knowledge_graph.json',data); write(mirror/f'{book}_middle_chunks.json',middle); return {'book':book,'path':str(graph_path),'mirror_path':str(mirror),**data['meta']}
def main():
 p=argparse.ArgumentParser(); p.add_argument('--deliverables',type=Path,default=DELIVERABLES); p.add_argument('--output-root',type=Path,default=OUTPUT); p.add_argument('--book',choices=BOOKS,action='append'); a=p.parse_args(); print(json.dumps({'success':True,'books':[build(x,a.deliverables,a.output_root) for x in (a.book or BOOKS)]},ensure_ascii=False,indent=2))
if __name__=='__main__': main()