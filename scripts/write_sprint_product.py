"""Write product decisions from completed evidence, not invented user impact."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    s2=json.loads((ROOT/'docs/sprint/S2_RESULTS/summary.json').read_text())
    s3=json.loads((ROOT/'docs/sprint/S3_RESULTS/summary.json').read_text())
    points=[r for r in s2['macro'] if r['group']=='all' and r['k'] in ['8','full']]
    points += [r for r in s3['macro'] if r['k']=='8' and r['method'] in ['router','oracle']]
    evidence=dict(sources=['docs/sprint/S1_SCOPE_EVIDENCE.md','docs/sprint/S2_RESULTS/summary.json',
                          'docs/sprint/S3_RESULTS/summary.json','docs/results/SOFTWARE_AND_STRESS_2026-10-22.md'],
                  points=points,h2=s2['h2']['verdict'],router_criterion=s3['verdict'],
                  practical_qualifying_budgets=s2['practical_qualifying_budgets'],
                  decision='NO-GO for replacing the current supervised prototype with a universal few-shot detector or the tested router',
                  user_interviews='planned, not done',organisation_count='not independently verified',
                  actual_factory_impact='not measured',operator_feedback='planned, not implemented as an automatic learning loop')
    (ROOT/'docs/sprint/S6_EVIDENCE.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    text='# Should few-shot onboarding replace full-data PatchCore?\n\n'
    text+='**Decision: '+evidence['decision']+'.**\n\n'
    text+='This decision concerns extensions of WCTE\'s inherited PatchCore system. Keep the shipped benchmark prototype supervised; the research recipes are offline comparisons, not a validated factory release. User interviews are planned, not done.\n\n'
    text+='Source tables: `S2_RESULTS/summary.json`, `S3_RESULTS/summary.json`; extracted decision inputs: `S6_EVIDENCE.json`.\n\n'
    text+='| Budget | Method | Macro AUROC | Category-bootstrap 95% interval |\n|---|---|---:|---|\n'
    for r in points:text+=f"| {r['k']} | {r['method']} | {r['mean']} | {r['ci95']} |\n"
    text+='\n## Why\n\n'
    text+='DINOv2 has the higher low-shot macro result, but neither recipe meets the registered all-category practical criterion. The full-shot H2 criterion is '+s2['h2']['verdict']+'. The tested normal-only router criterion is '+s3['verdict']+'. A favourable average can conceal an unsuitable part family. Recipes also differ in distance, aggregation and memory policy; this is not a pure causal backbone ablation. Extra normal calibration images are required beyond k.\n\n'
    text+='The prior synthetic blur study (`docs/results/SOFTWARE_AND_STRESS_2026-10-22.md`) found that blurred normal images became false alarms and the heuristic gate rejected none of the blurred images. RETAKE exists as a workflow state; it is not a demonstrated solution to blur. Keep manual review and test realistic capture conditions before promotion.\n\n'
    text+='## Product trade-off and next gate\n\n'
    text+='Fewer reference images could make onboarding easier, but neither onboarding time nor factory inspection quality has been measured. Keep the existing frozen detector as the benchmark default, continue few-shot research, and defer automatic routing. Do not claim an achieved operational saving.\n\n'
    text+='Agree a part family and error costs with a QA lead, collect separate development/test captures, and measure complete review tasks including retakes and corrections. The operator correction feature must preserve the original prediction. Curated feedback can support a later versioned model update; it must not silently change a deployed bank after a button click. No contact, pilot or deployment was performed by this memo.\n'
    (ROOT/'docs/sprint/S6_GO_NO_GO.md').write_text(text,encoding='utf-8')
    print(evidence['decision'])


if __name__=='__main__':main()
