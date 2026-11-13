#!/usr/bin/env python3
"""Integration regressions for state, memory, knowledge, blind packets, campaigns and exports."""
import importlib.util
import hashlib
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT/'skills/book-status/scripts/project_state.py'
spec = importlib.util.spec_from_file_location('state', SCRIPT)
s = importlib.util.module_from_spec(spec);spec.loader.exec_module(s)


class Workflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.root = Path(self.temp.name)
        shutil.copytree(ROOT/'tools/eval-fixtures/storycraft-book', self.root, dirs_exist_ok=True)
        self.chapter = 'Chapters/Book-1/Chapter-001.md'
        self.report = '_Edits/Book-1/Chapter-001_Gate.md'
        self.meta = self.report.replace('.md','.meta.json')

    def tearDown(self):
        self.temp.cleanup()

    def put(self,name,obj):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps({'schema_version':1,**obj}))
        return str(p)

    def runcli(self,*args,fail=False):
        r=subprocess.run([sys.executable,str(SCRIPT),'--root',str(self.root),*args],capture_output=True,text=True)
        if fail:
            self.assertNotEqual(r.returncode,0,r.stdout)
        else:
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        return json.loads(r.stdout)

    def review(self):
        spec=self.put('spec.json',dict(report=self.report,verdict='PASS',paths=[self.chapter,'Wiki/Characters','Wiki/Style/editorial-decisions.json']))
        self.runcli('prepare','--spec',spec,'--output','prepared.json')
        p=self.root/self.report;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('PASS\n')
        self.runcli('snapshot','--spec',str(self.root/'prepared.json'),'--output',self.meta)

    def test_freshness_content_not_timestamp(self):
        self.review();p=self.root/self.chapter;st=p.stat()
        os.utime(p,(st.st_atime+100,st.st_mtime+100))
        self.assertEqual(self.runcli('check','--meta',self.meta)['freshness'],'CURRENT')
        p.write_text(p.read_text()+'changed');os.utime(p,(st.st_atime,st.st_mtime))
        self.assertEqual(self.runcli('check','--meta',self.meta)['freshness'],'STALE')

    def test_readiness_requires_exact_review_subject(self):
        self.review()
        self.assertEqual(s.readiness(self.root,self.meta)['readiness'],'INELIGIBLE')
        result=s.readiness(self.root,self.meta,[self.chapter])
        self.assertEqual(result['readiness'],'ELIGIBLE')
        self.assertEqual(result['subject'],[self.chapter])

    def test_named_full_profile_cannot_clear_from_single_gate_report(self):
        self.review()
        result=s.readiness(self.root,self.meta,[self.chapter],profile='full_editorial_candidate')
        self.assertEqual(result['readiness'],'INELIGIBLE')
        self.assertIn('required profile lacks a linked operation journal',result['blocking_reasons'])
        unknown=s.readiness(self.root,self.meta,[self.chapter],profile='publication')
        self.assertEqual(unknown['readiness'],'INELIGIBLE')
        self.assertTrue(any('unknown readiness profile' in reason for reason in unknown['blocking_reasons']))

    def test_editorial_eval_separates_coverage_author_scores_and_repair_quality(self):
        cases=json.loads((ROOT/'tools/eval-fixtures/editorial-preservation/cases.json').read_text())['cases']
        case=next(item for item in cases if item['id']=='01-fix')
        opaque='opaque-case-1'
        config={'model':'fixture','temperature':0}
        config_hash=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        source_hash=hashlib.sha256(case['source'].encode()).hexdigest()
        mapping=self.put('.private-eval-map.json',dict(mapping={opaque:case['id']}))
        mapping_hash=hashlib.sha256(Path(mapping).read_bytes()).hexdigest()
        manifest=dict(run_id='RUN',corpus_sha256='corpus',expected_case_ids=[opaque],repeat_count=1,
            variants=['baseline','candidate'],source_hashes={opaque:source_hash},configuration=config,
            skill_hashes={'baseline':'a','candidate':'b'},packet_hashes={opaque:'packet'},
            span_policy='exact half-open unicode code points',permissions='fixture',permitted_context='adjacent prose',
            mapping_sha256=mapping_hash,
            required_author_dimensions=['voice','useful_repair'])
        results=[]
        for variant in manifest['variants']:
            result=dict(case_id=opaque,variant=variant,repeat_index=1,
                status='complete',source_sha256=source_hash,configuration_sha256=config_hash,
                packet_sha256='packet',attempt_id=variant+'-attempt',findings=[])
            if variant=='candidate':
                bad_span=case['defect_spans'][0]
                bad_start=case['source'].index(bad_span)
                result['findings']=[
                    dict(start=0,end=1,quote='e',replacement='nonsense',reason='substring-only probe'),
                    dict(start=bad_start,end=bad_start+len(bad_span),quote=bad_span,
                         replacement='utter nonsense',reason='damaging replacement'),
                ]
            else:
                result['status']='failed';result.pop('findings')
            results.append(result)
        # A later successful retry must not displace the first terminal failure.
        results.append(dict(case_id=opaque,variant='baseline',repeat_index=1,status='complete',
            source_sha256=source_hash,configuration_sha256=config_hash,packet_sha256='packet',
            attempt_id='favorable-retry',findings=[]))
        record=self.put('eval-results.json',dict(manifest=manifest,results=results))
        scored=subprocess.run([sys.executable,str(ROOT/'tools/eval-editorial.py'),'--results',record,
                               '--mapping',mapping],capture_output=True,text=True)
        self.assertEqual(scored.returncode,0,scored.stderr)
        report=json.loads(scored.stdout)
        self.assertEqual(report['coverage']['status'],'INCOMPLETE')
        self.assertEqual(len(report['coverage']['duplicates']),1)
        self.assertFalse(report['release_eligible'])
        self.assertEqual(report['author_evaluation'],'pending')
        self.assertEqual(report['counts']['author_scored'],0)
        self.assertEqual(report['counts']['localized_findings'],1)
        self.assertEqual(report['counts']['successful_repairs'],0)
        self.assertEqual(report['counts']['repair_judgments'],0)
        self.assertEqual(report['counts']['failed_runs'],1)
        self.assertEqual(report['counts']['scored_outputs'],1)
        record_data=json.loads(Path(record).read_text())
        record_data['semantic_judgments']=[dict(run_id='RUN',case_id=opaque,variant='candidate',repeat_index=1,
            attempt_id='candidate-attempt',finding_index=1,evaluator_role='editor',evaluator_id='editor-fixture',
            rubric_version='repair-v1',judgment='unsuccessful',rationale='The replacement damages the intended meaning.')]
        record_data['human_judgments']=[dict(run_id='RUN',case_id=opaque,variant='candidate',repeat_index=1,
            attempt_id='candidate-attempt',evaluator_role='author',evaluator_id='author-fixture',
            rubric_version='author-v1',dimension=dimension,accepted=False,reason='Fixture attribution only.')
            for dimension in ('voice','useful_repair')]
        Path(record).write_text(json.dumps(record_data))
        rescored=subprocess.run([sys.executable,str(ROOT/'tools/eval-editorial.py'),'--results',record,
                                 '--mapping',mapping],capture_output=True,text=True)
        self.assertEqual(rescored.returncode,0,rescored.stderr)
        revised=json.loads(rescored.stdout)
        self.assertEqual(revised['counts']['repair_judgments'],1)
        self.assertEqual(revised['counts']['successful_repairs'],0)
        self.assertEqual(revised['counts']['author_scored'],2)
        self.assertEqual(revised['counts']['author_unscored'],0)
        self.assertEqual(revised['author_evaluation'],'recorded')
        self.assertFalse(revised['release_eligible'])

    def test_legacy_and_new_directory_entry(self):
        self.assertEqual(self.runcli('check','--meta',self.meta)['freshness'],'UNKNOWN')
        self.review();p=self.root/'Wiki/Characters/Ren.md';p.parent.mkdir(parents=True);p.write_text('Ren')
        self.assertEqual(self.runcli('check','--meta',self.meta)['freshness'],'STALE')

    def test_report_mutation_and_review_race(self):
        self.review();(self.root/self.report).write_text('altered verdict')
        self.assertEqual(self.runcli('check','--meta',self.meta)['freshness'],'STALE')
        (self.root/self.chapter).write_text('author edit during review')
        self.runcli('snapshot','--spec',str(self.root/'prepared.json'),'--output',self.meta,fail=True)

    def test_schema_paths_and_lock(self):
        self.runcli('check','--meta','../escape.json',fail=True)
        self.put(self.meta,dict(schema_version=99))
        self.runcli('check','--meta',self.meta,fail=True)
        target=self.root/'test.json'
        with s.locked(target):
            with self.assertRaises(FileExistsError):
                with s.locked(target): pass

    def test_memory_scope_supersession_and_correctness(self):
        one=dict(id='D1',scope='Book-1/POV/Ren',rule_category='fragment',reason='explicit',status='active',reusable=True)
        spec=self.put('d.json',one)
        self.runcli('memory','--action','record','--spec',spec)
        self.runcli('memory','--action','record','--spec',spec)
        broad=dict(id='DS',scope='series',rule_category='style',reason='series rule',status='active',reusable=True)
        self.runcli('memory','--action','record','--spec',self.put('series.json',broad))
        book=dict(id='DB',scope='Book-1',rule_category='style',reason='book rule',status='active',reusable=True)
        self.runcli('memory','--action','record','--spec',self.put('book.json',book))
        self.assertEqual({x['id'] for x in self.runcli('memory','--scope','Book-1/POV/Ren')},{'D1','DS','DB'})
        self.assertEqual({x['id'] for x in self.runcli('memory','--scope','Book-1/POV/Mara')},{'DS','DB'})
        self.runcli('memory','--action','record','--spec',self.put('d.json',dict(one,id='D2',status='retired',supersedes=['D1'])))
        self.assertEqual({x['id'] for x in self.runcli('memory','--scope','Book-1/POV/Ren')},{'DS','DB'})
        self.runcli('memory','--action','record','--spec',self.put('d.json',dict(one,id='D3',rule_category='canon')),fail=True)
        self.runcli('memory','--action','record','--spec',self.put('d.json',dict(one,id='D4',supersedes=['missing'])),fail=True)

    def test_knowledge_false_belief_flashback_and_stale(self):
        event=dict(id='K1',fact_id='F1',observer='Mara',state='believes',story_position=[1,1],reader_position=[3,1],confirmed=True,source=self.chapter,source_sha256=s.digest(self.root/self.chapter),quote='Mara folded the receipt')
        self.runcli('knowledge','--action','record','--spec',self.put('k.json',event))
        self.assertEqual(self.runcli('knowledge','--action','as-of','--observer','Mara','--position','0'),{})
        self.assertEqual(self.runcli('knowledge','--action','as-of','--observer','Mara','--position','2')['F1']['state'],'believes')
        (self.root/self.chapter).write_text('changed')
        self.assertEqual(self.runcli('knowledge','--action','as-of','--observer','Mara','--position','2'),{})

    def test_relationships_carry_across_books_and_keep_plans_and_views_distinct(self):
        source=self.root/self.chapter
        common=dict(relationship_id='Mara-Ren',book_id='Book-1',source=self.chapter,
                    source_sha256=s.digest(source),quote='Mara folded the receipt')
        events=[
            dict(common,id='R1',observer='Mara',other='Ren',stance='allied',status='confirmed',
                 scene_id='B1-S9',story_order=50),
            dict(common,id='R2',observer='Ren',other='Mara',stance='distrustful',status='confirmed',
                 scene_id='B1-S9',story_order=55),
            dict(common,id='R3',observer='Mara',other='Ren',stance='betrayal',status='planned',
                 book_id='Book-2',scene_id='B2-S3',story_order=80),
        ]
        for event in events:
            self.runcli('relationship-state','--action','record','--spec',self.put('rel.json',event))
        mara=self.runcli('relationship-state','--observer','Mara','--scope','Ren','--story-order','60')
        self.assertEqual(mara['status'],'RESOLVED')
        self.assertEqual(mara['established'][0]['stance'],'allied')
        self.assertEqual(mara['planned_transitions'],[])
        ren=self.runcli('relationship-state','--observer','Ren','--scope','Mara','--story-order','60')
        self.assertEqual(ren['established'][0]['stance'],'distrustful')
        planned=self.runcli('relationship-state','--observer','Mara','--scope','Ren','--story-order','80','--scene-id','B2-S3')
        self.assertEqual(planned['established'][0]['stance'],'allied')
        self.assertEqual(planned['planned_transitions'][0]['stance'],'betrayal')

    def test_global_knowledge_uses_story_and_reader_positions_without_erasing_history(self):
        common=dict(fact_id='F-LETTER',truth_status='true',event_kind='belief_change',
                    source=self.chapter,source_sha256=s.digest(self.root/self.chapter),
                    quote='Mara folded the receipt',confirmed=True)
        for event in [
            dict(common,id='K-G1',observer='Mara',state='believes',story_order=10,reader_order=5),
            dict(common,id='K-G2',observer='Mara',state='knows',story_order=40,reader_order=20),
            dict(common,id='K-R1',observer='reader',state='exposed',story_order=40,reader_order=20),
        ]:
            self.runcli('knowledge-state','--action','record','--spec',self.put('event.json',event))
        early=self.runcli('knowledge-state','--observer','Mara','--story-order','20')
        self.assertEqual(early['state']['F-LETTER']['state'],'believes')
        late=self.runcli('knowledge-state','--observer','Mara','--story-order','50')
        self.assertEqual(late['state']['F-LETTER']['state'],'knows')
        reader_early=self.runcli('knowledge-state','--observer','reader','--reader-order','10')
        self.assertNotIn('F-LETTER',reader_early['state'])
        reader_late=self.runcli('knowledge-state','--observer','reader','--reader-order','25')
        self.assertEqual(reader_late['state']['F-LETTER']['state'],'exposed')

    def test_name_modes_preserve_attested_forms_and_report_shortfall(self):
        script=ROOT/'skills/name-generator/scripts/generate.py'
        evidence=self.put('names.json',{'records':[
            dict(source_id='SRC-1',exact_form='Éléonore de Valois',source_title='Register',source_locator='p. 4',
                 inspection_status='inspected',date_year=1420,region='France',language='French',historical_context='late medieval'),
            dict(source_id='SRC-2',exact_form='Anne-Marie',source_title='Parish register',source_locator='folio 8',
                 inspection_status='inspected',date_year=1430,region='France',language='French',historical_context='late medieval'),
            dict(source_id='SRC-3',exact_form='Modern only',source_title='Unknown',source_locator='?',
                 inspection_status='inspected',date_year=2020,region='France',language='French'),
        ]})
        command=[sys.executable,str(script),'--mode','historical_attested','--evidence',evidence,'--region','France',
                 '--language','French','--start-year','1400','--end-year','1450','--count','3','--seed','9','--json']
        r=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        result=json.loads(r.stdout)
        self.assertEqual({c['name'] for c in result['candidates']},{'Éléonore de Valois','Anne-Marie'})
        self.assertEqual(result['shortfall'],1)
        self.assertEqual(json.loads(subprocess.check_output(command,text=True))['candidates'],result['candidates'])
        self.assertEqual(result['attestation_validation'],'record eligibility only; source truth requires expert review')
        invented=[sys.executable,str(script),'--list',str(ROOT/'skills/name-generator/data/italian.txt'),
                  '--mode','invented','--count','3','--seed','17','--json']
        first=subprocess.check_output(invented,text=True)
        second=subprocess.check_output(invented,text=True)
        self.assertEqual(json.loads(first)['candidates'],json.loads(second)['candidates'])

    def test_nonfiction_evidence_requires_complete_anchored_inventory(self):
        script=ROOT/'skills/nonfiction-research/scripts/evidence.py'
        subject=self.root/self.chapter
        text=subject.read_text()
        quote1='Mara folded the receipt'
        quote2='Tomorrow she would tell him.'
        start1=text.index(quote1);start2=text.index(quote2)
        source_revision='snapshot-v1'
        record=dict(record_type='chapter_evidence',schema_version=1,record_id='CE1',project_id='P1',
            producer={'name':'test'},operation_id='OP1',subject_path=self.chapter,
            subject_sha256=s.digest(subject),sources=[dict(source_id='S1',source_type='archival_record',
                title='Inspected ledger',creator='Unknown',date='unknown',locator='archive/catalog/1',
                access_status='accessible',inspection_status='inspected',source_revision=source_revision,
                rights_status='permitted',limitations='Catalog locator only; context is limited.',
                passages=[dict(passage_id='P1',source_revision=source_revision,
                    quote='Mara folded the receipt')])],
            assertions=[dict(assertion_id='A1',claim_type='factual',load_bearing=True,
                anchor=dict(start=start1,end=start1+len(quote1),quote=quote1,subject_sha256=s.digest(subject))),
                dict(assertion_id='A2',claim_type='normative_judgment',load_bearing=False,
                anchor=dict(start=start2,end=start2+len(quote2),quote=quote2,subject_sha256=s.digest(subject)))],
            verifications=[dict(assertion_id='A1',result='verified',source_ids=['S1'],passage_ids=['P1'],
                evaluator='human-reviewer',rules_version='1',rationale='Passage directly supports the claim.'),
                dict(assertion_id='A2',result='not_empirical',evaluator='human-reviewer',rules_version='1',
                rationale='This is an explicitly normative interpretation.')],
            inventory_coverage=dict(complete=True,reviewer='human-reviewer',method='full-chapter semantic sweep',
                subject_sha256=s.digest(subject),omissions=[],limitations='Claims audited within chapter scope.'))
        record_path=self.put('evidence.json',record)
        r=subprocess.run([sys.executable,str(script),'--root',str(self.root),'--record',record_path],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        result=json.loads(r.stdout)
        self.assertEqual(result['readiness'],'ELIGIBLE')
        self.assertEqual(result['assertion_count'],2)
        record['verifications'][0]['source_ids']=['UNKNOWN']
        invalid_source=self.put('evidence.json',record)
        bad_source=subprocess.run([sys.executable,str(script),'--root',str(self.root),'--record',invalid_source],capture_output=True,text=True)
        self.assertTrue(any('unknown source' in reason for reason in json.loads(bad_source.stdout)['blocking_reasons']))
        record['verifications'][0]['source_ids']=['S1']
        record['inventory_coverage'].pop('limitations')
        no_limitations=self.put('evidence.json',record)
        incomplete=subprocess.run([sys.executable,str(script),'--root',str(self.root),'--record',no_limitations],capture_output=True,text=True)
        self.assertEqual(json.loads(incomplete.stdout)['coverage'],'INCOMPLETE')
        record['inventory_coverage']['limitations']='Claims audited within chapter scope.'
        record['verifications'].pop()
        record_path=self.put('evidence.json',record)
        blocked=subprocess.run([sys.executable,str(script),'--root',str(self.root),'--record',record_path],capture_output=True,text=True)
        self.assertEqual(json.loads(blocked.stdout)['readiness'],'INELIGIBLE')
        subject.write_text(text+'\nA changed assertion revision.')
        stale=subprocess.run([sys.executable,str(script),'--root',str(self.root),'--record',record_path],capture_output=True,text=True)
        self.assertIn('subject revision changed',json.loads(stale.stdout)['blocking_reasons'][0])

    def test_passage_extractor_is_wrap_stable_and_covers_sentence_splits(self):
        script=ROOT/'skills/book-status/scripts/passages.py'
        spec=importlib.util.spec_from_file_location('passages_test',script)
        passages=importlib.util.module_from_spec(spec);spec.loader.exec_module(passages)
        wrapped='The definition begins on this line and continues\nwith the same sentence, then ends. A second sentence follows.\n\nA new paragraph has its own context.'
        unwrapped='The definition begins on this line and continues with the same sentence, then ends. A second sentence follows.\n\nA new paragraph has its own context.'
        a=passages.extract(wrapped,chapter_id='C1',budget=50)
        b=passages.extract(unwrapped,chapter_id='C1',budget=50)
        first_a=[p for p in a['passages'] if p['parent_id']==a['passages'][0]['parent_id']]
        first_b=[p for p in b['passages'] if p['parent_id']==b['passages'][0]['parent_id']]
        self.assertEqual([p['normalized'] for p in first_a],[p['normalized'] for p in first_b])
        self.assertEqual(a['coverage'],'COMPLETE')
        self.assertTrue(all(p['text']==wrapped[p['start']:p['end']] for p in a['passages']))
        verse=passages.extract('Rain in the gutter\nA lamp in the window\nFootsteps pass',chapter_id='C1')
        self.assertEqual(verse['passages'][0]['kind'],'lineated')

    def test_ledger_generations_commit_atomically_and_retry_safely(self):
        module_path=ROOT/'skills/book-status/scripts/ledger_store.py'
        spec=importlib.util.spec_from_file_location('ledger_store_test',module_path)
        store=importlib.util.module_from_spec(spec);spec.loader.exec_module(store)
        (self.root/'Wiki').mkdir(exist_ok=True)
        tx=dict(transaction_id='TX1',expected_generation=None,source_evidence=s.evidence(self.root,[self.chapter]),
            updates={'Wiki/Story/knowledge-events.json':{'schema_version':1,'events':[{'id':'K1'}]},
                     'Wiki/Story/relationship-events.json':{'schema_version':1,'events':[{'id':'R1'}]},
                     'Wiki/Story/Book-1/promises.yaml':'promises:\n  - id: P1\n    promise: A committed promise\n    introduced_ch: ch1\n    payoff_by_ch: ch2\n'})
        committed=store.commit(self.root,tx)
        self.assertEqual(committed['status'],'COMMITTED')
        self.assertEqual(store.load_ledger(self.root,'Wiki/Story/knowledge-events.json')['events'][0]['id'],'K1')
        self.assertEqual(store.load_ledger(self.root,'Wiki/Story/relationship-events.json')['events'][0]['id'],'R1')
        promise_report=subprocess.run([sys.executable,str(ROOT/'skills/fiction-promises/scripts/promises.py'),
            '--book','Book-1'],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(promise_report.returncode,0,promise_report.stderr)
        self.assertIn('A committed promise',promise_report.stdout)
        self.assertEqual(store.commit(self.root,tx)['status'],'ALREADY_COMMITTED')
        altered=dict(tx,updates={'Wiki/Story/knowledge-events.json':{'schema_version':1,'events':[]}})
        with self.assertRaisesRegex(ValueError,'reused with different'):
            store.commit(self.root,altered)
        concurrent=dict(transaction_id='TX2',expected_generation='wrong',source_evidence=s.evidence(self.root,[self.chapter]),
            updates={'Wiki/Story/knowledge-events.json':{'schema_version':1,'events':[]}})
        with self.assertRaisesRegex(ValueError,'CONCURRENT_CHANGE'):
            store.commit(self.root,concurrent)
        no_source=dict(transaction_id='TX3',expected_generation=committed['generation_id'],source_evidence=[],
            updates={'Wiki/Story/knowledge-events.json':{'schema_version':1,'events':[]}})
        with self.assertRaisesRegex(ValueError,'source_evidence'):
            store.commit(self.root,no_source)
        lock_path=self.root/'.storycraft/ledger-current.json.lock'
        lock_fd=os.open(lock_path,os.O_CREAT|os.O_RDWR,0o600)
        try:
            fcntl.flock(lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            busy=dict(transaction_id='TX4',expected_generation=committed['generation_id'],
                source_evidence=s.evidence(self.root,[self.chapter]),updates={'Wiki/Story/knowledge-events.json':{'schema_version':1,'events':[{'id':'K2'}]}})
            with self.assertRaisesRegex(ValueError,'another ledger transaction'):
                store.commit(self.root,busy)
        finally:
            fcntl.flock(lock_fd,fcntl.LOCK_UN);os.close(lock_fd)
        self.assertEqual(store.status(self.root)['current_generation'],committed['generation_id'])

    def test_reading_no_future_and_restart(self):
        chapters=[f'Chapters/Book-1/Chapter-{n:03}.md' for n in (1,2,3)]
        first=self.root/chapters[0]
        first.write_text(first.read_text()+'\n<!-- STORYCRAFT: reader-private-sentinel -->\n')
        self.runcli('reading','--action','init','--spec',self.put('run.json',dict(chapters=chapters,reader_brief='Neutral genre reader')))
        packet=self.runcli('reading','--action','packet')
        self.assertNotIn('Jo had paid',json.dumps(packet))
        self.assertNotIn('reader-private-sentinel',json.dumps(packet))
        self.assertNotIn('source',packet)
        self.assertTrue((self.root/'_Edits/Book-1/reading/default/coordinator-001.json').is_file())
        reaction=dict(remembered_facts=[],predictions=['receipt matters'],questions=[],emotional_response='curious',continue_reading=True,confusion=[],relationship_changes=[],isolation_evidence={})
        self.runcli('reading','--action','seal','--spec',self.put('reaction.json',reaction),fail=True)
        reaction['isolation_evidence']=dict(verified_by_coordinator=True,transcript_reference='inspected-test-packet')
        self.runcli('reading','--action','seal','--spec',self.put('reaction.json',reaction))
        self.assertEqual(self.runcli('reading','--action','packet')['memory']['predictions'],['receipt matters'])
        (self.root/self.chapter).write_text('changed')
        self.runcli('reading','--action','packet',fail=True)

    def test_campaign_dependency_recovery_and_conflict(self):
        task=dict(id='setup',files=[self.chapter],depends_on=[])
        self.runcli('campaign','--action','init','--spec',self.put('c.json',dict(tasks=[task])))
        self.runcli('campaign','--action','start','--task','setup')
        self.runcli('campaign','--action','complete','--task','setup','--spec',self.put('checks.json',dict(checks=[])),fail=True)
        self.review()
        self.runcli('campaign','--action','complete','--task','setup','--spec',self.put('checks.json',dict(checks=[self.meta])))
        (self.root/self.chapter).write_text('later author change')
        self.runcli('campaign','--action','recover','--task','setup',fail=True)
        self.assertFalse(self.runcli('dashboard')['campaigns'][0]['current'])

    def test_campaign_cycles(self):
        self.runcli('campaign','--action','init','--spec',self.put('c.json',dict(tasks=[dict(id='x',files=[self.chapter],depends_on=['x'])])),fail=True)

    def test_pipeline_running_is_not_reusable(self):
        step=dict(record_type='pipeline_step',schema_version=2,id='draft',status='running',operation_id='default',idempotency_key='draft-1',
            completion_profile='draft_verified',stage_role='draft',subjects=[dict(id='chapter-1',path=self.chapter,
                sha256=s.digest(self.root/self.chapter))],
            constraints={'write_scope':'chapter'},inputs=s.evidence(self.root,[self.chapter]),
            authorized_writes=[self.chapter])
        self.runcli('pipeline','--action','record','--spec',self.put('step.json',step))
        self.assertFalse(self.runcli('pipeline')[0]['reusable'])
        source=self.root/self.chapter
        source.write_text(source.read_text()+'\nIn-place authorized edit.')
        step.update(status='complete',outputs=s.evidence(self.root,[self.chapter]))
        step['authorized_writes'].append('Chapters/Book-1/Chapter-002.md')
        self.runcli('pipeline','--action','record','--spec',self.put('step.json',step),fail=True)
        step['authorized_writes']=[self.chapter]
        self.runcli('pipeline','--action','record','--spec',self.put('step.json',step))
        self.assertTrue(self.runcli('pipeline')[-1]['reusable'])
        self.runcli('pipeline','--action','record','--spec',self.put('step.json',step))
        self.assertEqual(len(self.runcli('pipeline')),1)
        (self.root/self.chapter).write_text('changed')
        self.assertFalse(self.runcli('pipeline')[-1]['reusable'])

    def test_pipeline_keeps_historical_transform_lineage_after_later_edit(self):
        before=s.evidence(self.root,[self.chapter])[0]
        checkpoint='_Edits/Book-1/dev-checkpoint.md'
        step=dict(record_type='pipeline_step',schema_version=2,id='dev-repair',status='running',
            operation_id='history',idempotency_key='dev-repair-1',completion_profile='full_editorial_candidate',
            stage_role='developmental_repair',subjects=[dict(id='chapter-1',path=self.chapter,sha256=before['sha256'])],
            constraints={'scope':'chapter-only'},inputs=[before],authorized_writes=[self.chapter,checkpoint],
            transform_paths=[self.chapter])
        self.runcli('pipeline','--run','history','--action','record','--spec',self.put('dev-step.json',step))
        (self.root/self.chapter).write_text((self.root/self.chapter).read_text()+'\nDevelopmental repair.')
        checkpoint_path=self.root/checkpoint;checkpoint_path.parent.mkdir(parents=True,exist_ok=True)
        checkpoint_path.write_text('immutable checkpoint')
        step.update(status='complete',outputs=s.evidence(self.root,[checkpoint]),
            transformations=[dict(path=self.chapter,before=before,after=s.evidence(self.root,[self.chapter])[0])])
        self.runcli('pipeline','--run','history','--action','record','--spec',self.put('dev-step.json',step))
        self.assertTrue(self.runcli('pipeline','--run','history')[0]['reusable'])
        (self.root/self.chapter).write_text((self.root/self.chapter).read_text()+'\nA later line edit.')
        self.assertTrue(self.runcli('pipeline','--run','history')[0]['reusable'])

    def test_markdown_export_preserves_sources_and_release_blocks(self):
        exporter=ROOT/'skills/compile-manuscript/scripts/compile_manuscript.py'
        before=s.evidence(self.root,[self.chapter])
        def export(*extra):
            return subprocess.run([sys.executable,str(exporter),'--root',str(self.root),*extra],capture_output=True,text=True)
        r=export('--format','md');self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(before,s.evidence(self.root,[self.chapter]))
        output=self.root/'Chapters/Book-1/export/beta/manuscript-combined.md'
        self.assertLess(output.read_text().index('The Receipt'),output.read_text().index('The Letter'))
        export_manifest=json.loads((output.parent/'export-manifest.json').read_text())
        self.assertEqual(export_manifest['delivery_status'],'BUILT_PENDING_RENDERED_REVIEW')
        self.assertEqual(export_manifest['rendered_review']['formats']['md'],'PENDING')
        self.assertEqual(export_manifest['structural_checks']['md'],'PASS')
        original_package={p.name:p.read_bytes() for p in output.parent.iterdir() if p.is_file()}
        source_hash=s.digest(self.root/self.chapter)
        fake_bin=self.root/'fake-bin';fake_bin.mkdir()
        fake_pandoc=fake_bin/'pandoc'
        fake_pandoc.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo "pandoc test stub"; exit 0; fi\nexit 17\n')
        fake_pandoc.chmod(0o755)
        env=dict(os.environ,PATH=str(fake_bin)+os.pathsep+os.environ.get('PATH',''))
        failed=subprocess.run([sys.executable,str(exporter),'--root',str(self.root),'--format','docx'],
                              capture_output=True,text=True,env=env)
        self.assertNotEqual(failed.returncode,0)
        self.assertEqual(source_hash,s.digest(self.root/self.chapter))
        self.assertEqual(original_package,{p.name:p.read_bytes() for p in output.parent.iterdir()
                                           if p.is_file() and p.parent==output.parent})
        previous=sorted(output.parent.glob('beta.previous-*'))
        self.assertFalse(previous)
        self.assertNotEqual(export('--profile','publication').returncode,0)
        self.assertEqual(export('--profile','publication','--unchecked-preview').returncode,0)

    def test_upgrade_preserves_local_and_legacy(self):
        pinned=self.root/'.agents/skills';shutil.copytree(ROOT/'skills',pinned)
        local=pinned/'fiction-writechapter/SKILL.md';local.write_text('LOCAL CUSTOMIZATION')
        command=[sys.executable,str(ROOT/'tools/update-project.py'),str(self.root),'--apply']
        r=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('fiction-writechapter/SKILL.md',json.loads(r.stdout)['conflict'])
        self.assertEqual(local.read_text(),'LOCAL CUSTOMIZATION')

    def test_moved_root_still_current(self):
        self.review()
        moved = self.root/'moved'
        shutil.copytree(self.root, moved, ignore=shutil.ignore_patterns('moved'))
        self.assertEqual(s.freshness(moved, moved/self.meta)['freshness'],'CURRENT')

    def test_disposition_blocks_until_explicit_resolution(self):
        self.review()
        p=self.root/self.meta;meta=s.load(p);meta['findings']=[dict(id='G1',blocking=True)];s.write(p,meta)
        readiness=s.readiness(self.root,self.meta,[self.chapter])
        self.assertEqual(readiness['readiness'],'INELIGIBLE')
        self.assertEqual(readiness['blocking_findings'],['G1'])
        self.assertEqual(self.runcli('dashboard')['chapters'][0]['checks'][0]['blocking'],['G1'])
        item=dict(finding_id='G1',report=self.report,report_sha256=meta['report_sha256'],disposition='rejected',reason='Author resolved this finding explicitly')
        self.runcli('disposition','--spec',self.put('disposition.json',item))
        self.assertEqual(s.readiness(self.root,self.meta,[self.chapter])['readiness'],'ELIGIBLE')
        self.assertEqual(self.runcli('dashboard')['chapters'][0]['checks'][0]['blocking'],[])

    def test_knowledge_duplicate_event_rejected(self):
        event=dict(id='K1',fact_id='F1',observer='reader',state='exposed',story_position=[1],reader_position=[3],confirmed=True,source=self.chapter,source_sha256=s.digest(self.root/self.chapter),quote='Mara folded the receipt')
        spec=self.put('knowledge.json',event)
        self.runcli('knowledge','--action','record','--spec',spec)
        self.runcli('knowledge','--action','record','--spec',spec,fail=True)
        self.assertEqual(self.runcli('knowledge','--action','as-of','--observer','reader','--position','2'),{})

    def test_scene_break_and_system_preservation(self):
        source=self.root/self.chapter
        source.write_text(source.read_text()+'\n* * *\n\n> [!SYSTEM]\n> HP: 10\n\n<!-- STORYCRAFT: secret internal sentinel -->\n')
        exporter=ROOT/'skills/compile-manuscript/scripts/compile_manuscript.py'
        r=subprocess.run([sys.executable,str(exporter),'--root',str(self.root)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        output=(self.root/'Chapters/Book-1/export/beta/manuscript-combined.md').read_text()
        self.assertIn('HP: 10',output);self.assertIn('* * *',output);self.assertNotIn('secret internal sentinel',output)
        source.write_text(source.read_text()+'\n<!-- unclassified apparatus -->\n')
        preflight=subprocess.run([sys.executable,str(exporter),'--root',str(self.root),'--check'],capture_output=True,text=True)
        build=subprocess.run([sys.executable,str(exporter),'--root',str(self.root)],capture_output=True,text=True)
        self.assertNotEqual(preflight.returncode,0)
        self.assertNotEqual(build.returncode,0)
        self.assertIn('unknown HTML comment',preflight.stderr)
        self.assertIn('unknown HTML comment',build.stderr)

    def test_export_rejects_missing_and_duplicate_chapters(self):
        exporter=ROOT/'skills/compile-manuscript/scripts/compile_manuscript.py'
        shutil.copy2(self.root/self.chapter,self.root/'Chapters/Book-1/Chapter-1.md')
        r=subprocess.run([sys.executable,str(exporter),'--root',str(self.root),'--check'],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0)

    def test_update_uses_recorded_base(self):
        pinned=self.root/'.agents/skills';shutil.copytree(ROOT/'skills',pinned)
        target=pinned/'fiction-dialogue/SKILL.md'
        base={str(p.relative_to(pinned)):s.digest(p) for p in pinned.rglob('*') if p.is_file()}
        (pinned/'.storycraft-base.json').write_text(json.dumps(base))
        target.write_text('MY LOCAL RULES')
        r=subprocess.run([sys.executable,str(ROOT/'tools/update-project.py'),str(self.root),'--apply','--prune'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(target.read_text(),'MY LOCAL RULES')
        self.assertIn('fiction-dialogue/SKILL.md',json.loads(r.stdout)['conflict'])

    def test_editorial_scoring_does_not_invent_author_acceptance(self):
        result=self.put('results.json',dict(configuration={'host':'recorded-test'},repeat_count=1,results=[dict(id='01-fix',findings=[{'quote':'not in source','replacement':'x'}])]))
        r=subprocess.run([sys.executable,str(ROOT/'tools/eval-editorial.py'),'--results',result],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        score=json.loads(r.stdout)
        self.assertEqual(score['counts']['unsupported_quotes'],1)
        self.assertEqual(score['author_evaluation'],'pending')
        self.assertIsNone(score['author_acceptance'])

    def test_evaluation_incomplete_coverage_cannot_be_release_eligible(self):
        cases=json.loads((ROOT/'tools/eval-fixtures/editorial-preservation/cases.json').read_text())['cases']
        case=next(c for c in cases if c['id']=='01-fix')
        source_hash=__import__('hashlib').sha256(case['source'].encode()).hexdigest()
        configuration={'host':'recorded-test','model':'recorded-model'}
        config_hash=__import__('hashlib').sha256(json.dumps(configuration,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        packet_hash='a'*64
        opaque='opaque-01'
        mapping=self.put('private-map.json',dict(mapping={opaque:'01-fix'}))
        mapping_hash=hashlib.sha256(Path(mapping).read_bytes()).hexdigest()
        result=self.put('results.json',dict(configuration=configuration,repeat_count=2,run_id='RUN1',
            corpus_sha256='b'*64,source_hashes={opaque:source_hash},skill_hashes={'editor':'c'*64},
            packet_hashes={opaque:packet_hash},mapping_sha256=mapping_hash,span_policy='exact half-open codepoint offsets',
            permissions='fixture corpus authorized',permitted_context='source and declared rules',
            expected_case_ids=[opaque],variants=['baseline','candidate'],
            results=[dict(case_id=opaque,variant='baseline',repeat_index=1,
                          status='complete',findings=[],source_sha256=source_hash,
                          configuration_sha256=config_hash,packet_sha256=packet_hash,attempt_id='A1')]))
        r=subprocess.run([sys.executable,str(ROOT/'tools/eval-editorial.py'),'--results',result,
                          '--mapping',mapping],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        score=json.loads(r.stdout)
        self.assertEqual(score['coverage']['status'],'INCOMPLETE')
        self.assertEqual(len(score['coverage']['missing']),3)
        self.assertFalse(score['release_eligible'])

    def test_reader_text_extractor_fails_closed_and_preserves_displays(self):
        extractor_path=ROOT/'skills/book-status/scripts/reader_text.py'
        spec=importlib.util.spec_from_file_location('reader_text',extractor_path)
        extractor=importlib.util.module_from_spec(spec);spec.loader.exec_module(extractor)
        raw='Letter <!-- STORYCRAFT:\nprivate sentinel --> end\n\n* * *\n\n> [!SYSTEM]\n> HP: 10\n'
        result=extractor.extract(raw,source='chapter.md')
        self.assertNotIn('private sentinel',result['text'])
        self.assertIn('HP: 10',result['text'])
        self.assertIn('* * *',result['text'])
        self.assertIn('Letter  end',result['text'])
        with self.assertRaisesRegex(ValueError,'chapter.md:1: unknown HTML comment'):
            extractor.extract('<!-- unknown -->\ntext',source='chapter.md')
        with self.assertRaisesRegex(ValueError,'unclosed fenced block'):
            extractor.extract('```storycraft-internal\nsecret',source='chapter.md')

    def test_manifest_preview_apply_and_idempotent_resolution(self):
        command=[sys.executable,str(ROOT/'tools/project-manifest.py'),str(self.root)]
        preview=subprocess.run(command+['preview'],capture_output=True,text=True)
        self.assertEqual(preview.returncode,0,preview.stderr)
        self.assertEqual(json.loads(preview.stdout)['status'],'preview')
        manifest_path=self.root/'.storycraft/project.json'
        self.assertFalse(manifest_path.exists())
        applied=subprocess.run(command+['apply'],capture_output=True,text=True)
        self.assertEqual(applied.returncode,0,applied.stderr)
        manifest=json.loads(applied.stdout)['manifest']
        self.assertEqual(len(manifest['books'][0]['chapters']),3)
        second=subprocess.run(command+['apply'],capture_output=True,text=True)
        self.assertEqual(second.returncode,0,second.stderr)
        self.assertEqual(json.loads(second.stdout)['status'],'already_applied')
        exporter=subprocess.run([sys.executable,str(ROOT/'skills/compile-manuscript/scripts/compile_manuscript.py'),
                                 '--root',str(self.root),'--format','md','--check'],capture_output=True,text=True)
        self.assertEqual(exporter.returncode,0,exporter.stderr)
        self.assertEqual(len(json.loads(exporter.stdout)['sources']),3)
        resolver_path=ROOT/'skills/book-status/scripts/project_manifest.py'
        spec=importlib.util.spec_from_file_location('project_manifest_test',resolver_path)
        resolver=importlib.util.module_from_spec(spec);spec.loader.exec_module(resolver)
        self.assertEqual([c['reading_order'] for c in resolver.chapters(self.root,'Book-1')],[1,2,3])
        outside=Path(self.temp.name).parent/'storycraft-outside-test.md'
        try:
            outside.write_text('outside')
            with self.assertRaisesRegex(ValueError,'escapes project root'):
                resolver.contained(self.root,'../storycraft-outside-test.md')
        finally:
            outside.unlink(missing_ok=True)

    def test_manifest_rejects_duplicate_authority_and_predecessor_cycles(self):
        resolver_path=ROOT/'skills/book-status/scripts/project_manifest.py'
        spec=importlib.util.spec_from_file_location('project_manifest_negative_test',resolver_path)
        resolver=importlib.util.module_from_spec(spec);spec.loader.exec_module(resolver)
        chapters=[]
        for number in (1,2):
            rel=f'Chapters/Book-1/Chapter-{number:03}.md'
            target=self.root/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(f'Chapter {number}.')
            chapters.append(dict(id=f'C{number}',path=rel,reading_order=number,predecessor_id=None))
        base=dict(record_type='project_manifest',schema_version=1,project_id='P',books=[
            dict(id='B1',chapters=chapters),dict(id='B2',chapters=[dict(id='C3',path=chapters[0]['path'],reading_order=1)])])
        with self.assertRaisesRegex(ValueError,'duplicate authoritative chapter path'):
            resolver.validate(base,self.root)
        base['books']=base['books'][:1]
        chapters[0]['predecessor_id']='C2';chapters[1]['predecessor_id']='C1'
        with self.assertRaisesRegex(ValueError,'predecessor cycle'):
            resolver.validate(base,self.root)
        # Reading order is scoped to a book; both books may begin at order 1.
        chapters[0]['predecessor_id']=None;chapters[1]['predecessor_id']='C1'
        base['books'].append(dict(id='B2',chapters=[dict(id='C3',path='Chapters/Book-2/Chapter-001.md',reading_order=1)]))
        p=self.root/'Chapters/Book-2/Chapter-001.md';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('Other book.')
        self.assertEqual(resolver.validate(base,self.root)['books'][1]['chapters'][0]['reading_order'],1)
        outside=Path(self.temp.name).parent/(Path(self.temp.name).name+'-symlink-outside.md')
        link=self.root/'Chapters/Book-2/escape.md'
        outside_dir=Path(self.temp.name).parent/(Path(self.temp.name).name+'-symlink-dir')
        nested_link=self.root/'Chapters/Book-2/linked-dir'
        try:
            outside.write_text('outside');link.symlink_to(outside)
            with self.assertRaisesRegex(ValueError,'escapes project root'):
                resolver.contained(self.root,'Chapters/Book-2/escape.md')
            outside_dir.mkdir(exist_ok=True);nested_link.symlink_to(outside_dir,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'escapes project root'):
                resolver.contained(self.root,'Chapters/Book-2/linked-dir/child.md')
        finally:
            link.unlink(missing_ok=True);nested_link.unlink(missing_ok=True)
            outside.unlink(missing_ok=True);outside_dir.rmdir()

    def test_style_authority_resolves_import_alias_and_surfaces_conflicts(self):
        resolver_path=ROOT/'skills/book-status/scripts/project_manifest.py'
        spec=importlib.util.spec_from_file_location('project_manifest_style_test',resolver_path)
        resolver=importlib.util.module_from_spec(spec);spec.loader.exec_module(resolver)
        style_dir=self.root/'Wiki/Style';style_dir.mkdir(parents=True,exist_ok=True)
        imported=style_dir/'style.md';imported.write_text('Distinctive imported rule: keep the narrator dry.')
        resolved=resolver.resolve_style_guide(self.root,'Book-1')
        self.assertEqual(resolved['status'],'RESOLVED')
        self.assertEqual(resolved['path'],'Wiki/Style/style.md')
        packet=self.runcli('draft-packet','--chapter','1')
        self.assertEqual(packet['style_authority']['path'],'Wiki/Style/style.md')
        canonical=style_dir/'style_guide.md';canonical.write_text('A conflicting authority.')
        conflict=resolver.resolve_style_guide(self.root,'Book-1')
        self.assertEqual(conflict['status'],'CONFLICT')
        self.assertEqual(len(conflict['paths']),2)
        packet=self.runcli('draft-packet','--chapter','1')
        self.assertEqual(packet['style_authority']['status'],'CONFLICT')

    def test_manifest_custom_display_order_drives_draft_packet_and_predecessor(self):
        records=[]
        for cid,label,rel,order,predecessor in (
            ('C-A','Chapter 1.5','Chapters/Book-1/custom/first.md',10,None),
            ('C-I','Interlude','Chapters/Book-1/insert/interlude.md',20,'C-A')):
            path=self.root/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(f'{label} prose. It continues.')
            records.append(dict(id=cid,display_label=label,path=rel,reading_order=order,predecessor_id=predecessor))
        plan='Wiki/Outline/Book-1/interlude-plan.md'
        plan_path=self.root/plan;plan_path.parent.mkdir(parents=True,exist_ok=True);plan_path.write_text('POV: Mara\n\n## Scene 1\n')
        records[1]['scene_plan_path']=plan
        manifest=dict(record_type='project_manifest',schema_version=1,project_id='P-custom',record_id='M1',
            books=[dict(id='B1',display_label='Book-1',chapters=records)])
        manifest_path=self.root/'.storycraft/project.json';manifest_path.parent.mkdir(parents=True,exist_ok=True)
        manifest_path.write_text(json.dumps(manifest))
        packet_result=subprocess.run([sys.executable,str(SCRIPT),'--root',str(self.root),'--book','Book-1',
                                      'draft-packet','--chapter','Interlude'],capture_output=True,text=True)
        self.assertEqual(packet_result.returncode,0,packet_result.stdout+packet_result.stderr)
        packet=json.loads(packet_result.stdout)
        self.assertEqual(packet['chapter_id'],'C-I')
        self.assertEqual(packet['chapter_path'],records[1]['path'])
        self.assertEqual(packet['predecessor_id'],'C-A')
        self.assertEqual(packet['continuity_tail']['path'],records[0]['path'])
        self.assertEqual(packet['scene_plan']['path'],plan)

    def test_draft_packet_checkpoints_cooling_and_psych(self):
        char_md = self.root / 'Wiki/Characters/Mara.md'
        char_md.parent.mkdir(parents=True, exist_ok=True)
        char_md.write_text(
            '---\nname: Mara\nrole: protagonist\n---\n\n'
            '## relationship_checkpoints\n\n'
            '### Jo\n'
            '- **link_type:** rival\n'
            '- **chapter_start:** 1\n'
            '- **chapter_end:** 2\n'
            '- **notes:** Distrusts Jo over the ledger\n'
            '- **link_type:** ally\n'
            '- **chapter_start:** 3\n'
            '- **chapter_end:** (open)\n'
            '- **notes:** Uneasy truce after the receipt reveal\n'
        )
        style_md = self.root / 'Wiki/Style/style_guide.md'
        style_md.parent.mkdir(parents=True, exist_ok=True)
        style_md.write_text('---\npov_mode: dual\npov_1: Mara\npov_2: Jo\n---\n\n## Style\nClose third past.\n')
        decisions_path=self.root/'Wiki/Style/editorial-decisions.json'
        decisions_path.write_text(json.dumps({'schema_version':1,'decisions':[
            dict(id='SERIES',scope='series',status='active',rule_category='style'),
            dict(id='BOOK',scope='Book-1',status='active',rule_category='style'),
            dict(id='CH3',scope='Book-1/Chapter-003',status='active',rule_category='style'),
            dict(id='MARA',scope='Book-1/POV/Mara',status='active',rule_category='style'),
            dict(id='OTHER',scope='Book-2/POV/Mara',status='active',rule_category='style'),
        ]}))
        vp_mara = self.root / 'Wiki/Style/voice_prompt_Mara.md'
        vp_mara.write_text('# Voice Prompt: Mara\n')
        psych_md = self.root / 'Wiki/Psych/Book-1/Chapter_03_Psych.md'
        psych_md.parent.mkdir(parents=True, exist_ok=True)
        psych_md.write_text(
            '# Chapter 03: Psychological Interior Pass\n'
            '**POV:** Mara, 29\n\n'
            '## Beat-by-Beat Interior Cost\n'
            '### The Receipt\n'
            "- **Interior cost:** Grief\n"
            "- **Body expression:** Hands still\n"
            "- **What they won't say:** I still blame you for the fire.\n\n"
            "## Show-Don't-Tell Gaps\n"
            '| Beat | What a reporting draft does | What it should do instead |\n'
            '|------|----------------------------|--------------------------|\n'
            '| Jo enters | States she is angry | Pockets the key without looking up |\n'
        )
        ch1 = self.root / 'Chapters/Book-1/Chapter-001.md'
        ch2 = self.root / 'Chapters/Book-1/Chapter-002.md'
        ch1.write_text(
            '# Chapter 1\n\n'
            'Mara folded the receipt and clenched her jaw. Her jaw ached.\n\n'
            '> [!SYSTEM]\n'
            '> ZORBAXICUS_SENTINEL jaw jaw jaw\n'
        )
        ch2.write_text(
            '# Chapter 2\n\n'
            'Mara folded the receipt again. Her jaw tightened in the hall.\n'
        )
        pkt1 = self.runcli('draft-packet', '--chapter', '1')
        self.assertEqual(len(pkt1['relationship_checkpoints']), 1)
        self.assertEqual(pkt1['relationship_checkpoints'][0]['link_type'], 'rival')

        pkt3 = self.runcli(
            'draft-packet', '--chapter', '3',
            '--output', '_Edits/Book-1/packets/Chapter-003_DraftPacket.json'
        )
        self.assertTrue((self.root / '_Edits/Book-1/packets/Chapter-003_DraftPacket.json').is_file())
        self.assertEqual(len(pkt3['relationship_checkpoints']), 1)
        self.assertEqual(pkt3['relationship_checkpoints'][0]['link_type'], 'ally')
        self.assertEqual(pkt3['psych']['what_they_wont_say'], ['I still blame you for the fire.'])
        self.assertEqual(len(pkt3['psych']['show_dont_tell_gaps']), 1)
        self.assertEqual({d['id'] for d in pkt3['editorial_decisions']},{'SERIES','BOOK','CH3','MARA'})
        self.assertTrue(any(v['path'] == 'Wiki/Style/voice_prompt_Mara.md' for v in pkt3['voice_prompts']))
        hot_words = [h['word'] for h in pkt3['cooling_list']['somatic_hotspots']]
        self.assertIn('jaw', hot_words)
        ngrams = [g['ngram'] for g in pkt3['cooling_list']['repeated_ngrams']]
        self.assertIn('folded the receipt', ngrams)
        self.assertNotIn('ZORBAXICUS', json.dumps(pkt3).upper())


if __name__ == '__main__':
    unittest.main()
