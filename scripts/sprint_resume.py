"""Generate resume statements only from completed, source-linked evidence."""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def main():
    def read(name):return json.loads((ROOT/name).read_text())
    s2=read('docs/sprint/S2_RESULTS/summary.json');s3=read('docs/sprint/S3_RESULTS/summary.json')
    s4=read('docs/sprint/S4_RESULTS/summary.json')
    def point(method,group='all'):
        return next(r for r in s2['macro'] if r['method']==method and r['group']==group and r['k']=='8')
    d,p=point('dinov2_vits14'),point('patchcore_wrn50')
    router=next(r for r in s3['macro'] if r['method']=='router' and r['k']=='8')
    count=len(d['categories'])
    suites=list(ET.parse(ROOT/'artifacts/sprint-2026-11-01/s6-tests.xml').getroot().iter('testsuite'))
    assert all(int(s.get('failures',0))==0 and int(s.get('errors',0))==0 for s in suites)
    tests=sum(int(s.get('tests',0))-int(s.get('skipped',0)) for s in suites)
    log=(ROOT/'artifacts/sprint-2026-11-01/s7-frontend/console.log').read_text()
    frontend=int(re.search(r'(\d+) frontend regression checks passed',log).group(1))
    bottle=next(r for r in s4['models'] if r['category']=='bottle')
    n=sum(r['images'] for r in s4['models']);agree=sum(r['agreeing_decisions'] for r in s4['models'])
    interval=lambda r:f"[{r['ci95'][0]:.4f}, {r['ci95'][1]:.4f}]"
    values={
      'S1':dict(status='numeric reach not supported',resume_line=None,
                reason='No independently verified WCTE organisation count or sector target was found.',sources=['docs/sprint/S1_SCOPE_EVIDENCE.md']),
      'S2':dict(status='supported benchmark claim',
                resume_line=f"Benchmarked training-free DINOv2 against inherited WCTE PatchCore across {count} MVTec AD categories (k=1-16, three seeds): k=8 macro AUROC {d['mean']:.4f} (95% category-bootstrap CI {interval(d)}) versus {p['mean']:.4f} ({interval(p)}), with a higher DINOv2 texture-category mean.",
                sources=['docs/sprint/S2_RESULTS/summary.json'],
                limitation='k counts reference images, not the additional normal-calibration images. Registered practical-use and H2 criteria were not met. Previously inspected v1 results are disclosed.'),
      'S3':dict(status='supported negative exploratory result',
                resume_line=f"Evaluated a fixed normal-validation-only backbone selector across {count} categories: k=8 macro AUROC {router['mean']:.4f} versus {d['mean']:.4f} for fixed DINOv2; rejected the selector after its registered comparison criterion failed.",
                sources=['docs/sprint/S3_RESULTS/summary.json'],limitation='Previously inspected benchmark; no trained cross-category meta-model or unseen-category confirmation.'),
      'S4':dict(status='supported export candidate, not device deployment',
                resume_line=f"Built a FastAPI inspection workflow, offline bundles and Android companion around inherited WCTE PatchCore; verified an ONNX candidate with {agree}/{n} held-out decisions preserved and bottle CPU model-call p50/p95 {bottle['timing_ms']['onnx']['p50']:.1f}/{bottle['timing_ms']['onnx']['p95']:.1f} ms; {tests} Python tests and {frontend} frontend checks in CI.",
                sources=['docs/sprint/S4_RESULTS/summary.json','docs/ANDROID_COMPANION.md','docs/results/SOFTWARE_AND_STRESS_2026-10-22.md',
                         'artifacts/sprint-2026-11-01/s6-tests.xml','artifacts/sprint-2026-11-01/s7-frontend/console.log'],
                limitation='Warm laptop model calls; decoding/network/UI excluded. No phone or glasses timing. Serving app not switched to the new ONNX candidate.'),
      'S5':dict(status='live public hosting not supported',
                resume_line='Prepared and locally tested a sample-only inference demo with a separate generated reference bank and an allowlisted Docker review package; public deployment remains pending.',
                sources=['docs/sprint/S5_RESULTS/status.json'],reason='No public deployment approval or account plan confirmed; no container build or public endpoint is claimed.'),
      'S6':dict(status='supported product planning, not user impact',
                resume_line='Defined product requirements and go/no-go decisions for a WCTE inspection prototype extending inherited PatchCore; retained supervised review after blur-stress and few-shot findings, with inspector interviews and factory impact measurement still planned.',
                sources=['docs/sprint/S6_PRD.md','docs/sprint/S6_GO_NO_GO.md','docs/sprint/S6_EVIDENCE.json'],
                limitation='No verified organisation count, end-user research, saved onboarding time or industrial impact. RETAKE is not a validated blur solution.')}
    result=dict(items=values,python_tests=tests,frontend_checks=frontend,
                scope='Statements distinguish inherited detector code from project extensions; no publication, factory pilot or public deployment is claimed.')
    target=ROOT/'docs/sprint/RESUME_EVIDENCE.json'
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# Sprint resume evidence','',result['scope'],'']
    for key,r in values.items():
        lines += [f"## {key}: {r['status']}",'',r.get('resume_line') or 'Not supported: '+r['reason'],'',
                  'Sources: '+', '.join('`'+x+'`' for x in r['sources'])+'.','',r.get('limitation',r.get('reason','')),'']
    (ROOT/'docs/sprint/RESUME_EVIDENCE.md').write_text('\n'.join(lines),encoding='utf-8')
    print(target)


if __name__=='__main__':main()
