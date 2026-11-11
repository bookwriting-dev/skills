#!/usr/bin/env python3
"""Integration regressions for state, memory, knowledge, blind packets, campaigns and exports."""
import importlib.util
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
        self.runcli('memory','--action','record','--spec',self.put('d.json',one))
        self.assertEqual(self.runcli('memory','--scope','Book-1/POV/Mara'),[])
        self.runcli('memory','--action','record','--spec',self.put('d.json',dict(one,id='D2',status='retired',supersedes=['D1'])))
        self.assertEqual(self.runcli('memory','--scope','Book-1/POV/Ren'),[])
        self.runcli('memory','--action','record','--spec',self.put('d.json',dict(one,id='D3',rule_category='canon')),fail=True)

    def test_knowledge_false_belief_flashback_and_stale(self):
        event=dict(id='K1',fact_id='F1',observer='Mara',state='believes',story_position=[1,1],reader_position=[3,1],confirmed=True,source=self.chapter,source_sha256=s.digest(self.root/self.chapter),quote='Mara folded the receipt')
        self.runcli('knowledge','--action','record','--spec',self.put('k.json',event))
        self.assertEqual(self.runcli('knowledge','--action','as-of','--observer','Mara','--position','0'),{})
        self.assertEqual(self.runcli('knowledge','--action','as-of','--observer','Mara','--position','2')['F1']['state'],'believes')
        (self.root/self.chapter).write_text('changed')
        self.assertEqual(self.runcli('knowledge','--action','as-of','--observer','Mara','--position','2'),{})

    def test_reading_no_future_and_restart(self):
        chapters=[f'Chapters/Book-1/Chapter-{n:03}.md' for n in (1,2,3)]
        self.runcli('reading','--action','init','--spec',self.put('run.json',dict(chapters=chapters,reader_brief='Neutral genre reader')))
        packet=self.runcli('reading','--action','packet')
        self.assertNotIn('Jo had paid',json.dumps(packet))
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
        step=dict(id='draft',status='running',inputs=s.evidence(self.root,[self.chapter]))
        self.runcli('pipeline','--action','record','--spec',self.put('step.json',step))
        self.assertFalse(self.runcli('pipeline')[0]['reusable'])
        step.update(status='complete',outputs=s.evidence(self.root,[self.chapter]))
        self.runcli('pipeline','--action','record','--spec',self.put('step.json',step))
        self.assertTrue(self.runcli('pipeline')[-1]['reusable'])
        (self.root/self.chapter).write_text('changed')
        self.assertFalse(self.runcli('pipeline')[-1]['reusable'])

    def test_markdown_export_preserves_sources_and_release_blocks(self):
        exporter=ROOT/'skills/compile-manuscript/scripts/compile_manuscript.py'
        before=s.evidence(self.root,[self.chapter])
        def export(*extra):
            return subprocess.run([sys.executable,str(exporter),'--root',str(self.root),*extra],capture_output=True,text=True)
        r=export('--format','md');self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(before,s.evidence(self.root,[self.chapter]))
        output=self.root/'Chapters/Book-1/export/beta/manuscript-combined.md'
        self.assertLess(output.read_text().index('The Receipt'),output.read_text().index('The Letter'))
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
        self.assertEqual(self.runcli('dashboard')['chapters'][0]['checks'][0]['blocking'],['G1'])
        item=dict(finding_id='G1',report=self.report,report_sha256=meta['report_sha256'],disposition='rejected',reason='Author resolved this finding explicitly')
        self.runcli('disposition','--spec',self.put('disposition.json',item))
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
        self.assertTrue(any(v['path'] == 'Wiki/Style/voice_prompt_Mara.md' for v in pkt3['voice_prompts']))
        hot_words = [h['word'] for h in pkt3['cooling_list']['somatic_hotspots']]
        self.assertIn('jaw', hot_words)
        ngrams = [g['ngram'] for g in pkt3['cooling_list']['repeated_ngrams']]
        self.assertIn('folded the receipt', ngrams)
        self.assertNotIn('ZORBAXICUS', json.dumps(pkt3).upper())


if __name__ == '__main__':
    unittest.main()
