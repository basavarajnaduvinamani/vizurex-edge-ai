"""Inspect every historical Phase 1 error against this session's fresh seed-0 run."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from PIL import Image, ImageDraw
import numpy as np
from torchvision import transforms

ROOT=Path(__file__).resolve().parents[1]


def main():
    out=ROOT/'results/2026-10-30/step4';out.mkdir(parents=True,exist_ok=True)
    private=ROOT/'artifacts/upgrade-2026-10-30/error-images';private.mkdir(parents=True,exist_ok=True)
    crop=transforms.Compose([transforms.Resize(256),transforms.CenterCrop(224)])
    mask_resize=transforms.Resize(256,interpolation=transforms.InterpolationMode.NEAREST)
    rows=[]
    for category in ['bottle','grid','transistor']:
        oldpath=ROOT/f'artifacts/phase1-20261021/runs/{category}/evaluation/mvtec_{category}_predictions.csv'
        old=list(csv.DictReader(oldpath.open()))
        freshpath=ROOT/f'results/2026-10-30/step1/{category}_seed0_current/predictions.csv'
        fresh={r['image']:r for r in csv.DictReader(freshpath.open())}
        threshold=json.loads(freshpath.with_name('summary.json').read_text())['metrics']['threshold']
        for r in old:
            if r['Correct']=='Yes':continue
            path=ROOT/'data/raw/mvtec_ad'/category/'test'/r['Image']
            with Image.open(path) as im:
                original_size=list(im.size);cropped=crop(im.convert('RGB'))
            target=private/(category+'_'+r['Image'].replace('/','_'))
            cropped.save(target)
            mask_path=ROOT/'data/raw/mvtec_ad'/category/'ground_truth'/Path(r['Image']).parent/(Path(r['Image']).stem+'_mask.png')
            retention=None;before=None;after=None
            if mask_path.exists():
                with Image.open(mask_path) as im:
                    resized=mask_resize(im.convert('L'))
                    before=int((np.asarray(resized)>0).sum())
                    after=int((np.asarray(transforms.CenterCrop(224)(resized))>0).sum())
                retention=after/before if before else None
            new=fresh[r['Image']]
            kind='missed_defect' if r['GT']=='ANOMALY' else 'false_alarm'
            # Causes beyond complete removal of the annotated region require
            # visual review or a controlled follow-up, never causal invention.
            classification='annotated_defect_outside_model_crop' if after==0 and before else (
                'visible_annotated_defect_below_threshold' if kind=='missed_defect' else
                'normal_sample_above_validation_threshold')
            rows.append(dict(category=category,image=r['Image'],historical_error=kind,
                new_label=new['label'],new_predicted=new['predicted'],new_score=new['score'],
                frozen_threshold=threshold,original_image_size=original_size,
                image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                resized_mask_pixels=before,cropped_mask_pixels=after,annotated_mask_retention=retention,
                classification=classification,root_cause='UNKNOWN except directly measured crop removal',
                visual_review='PENDING',crop_path=str(target.relative_to(ROOT)),
                crop_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                historical_source=str(oldpath.relative_to(ROOT)),new_source=str(freshpath.relative_to(ROOT))))
    result=dict(command=[sys.executable,*sys.argv],seed=0,
        execution_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        cases=rows,total_cases=len(rows),
        historical_missed_defects=sum(r['historical_error']=='missed_defect' for r in rows),
        historical_false_alarms=sum(r['historical_error']=='false_alarm' for r in rows),
        policy='Retrospective error analysis only; no thresholds or models changed. This test set is not a development set.')
    sheets=[]
    for page, start in enumerate(range(0,len(rows),5)):
        canvas=Image.new('RGB',(650,290*min(5,len(rows)-start)), 'white')
        draw=ImageDraw.Draw(canvas)
        for slot,row in enumerate(rows[start:start+5]):
            y=slot*290
            draw.text((5,y+3),row['category']+' / '+row['image']+' / '+row['historical_error'],fill='black')
            source=ROOT/'data/raw/mvtec_ad'/row['category']/'test'/row['image']
            with Image.open(source) as im:
                thumbnail=im.convert('RGB');thumbnail.thumbnail((290,240));canvas.paste(thumbnail,(5,y+35))
            with Image.open(ROOT/row['crop_path']) as im:
                canvas.paste(im.convert('RGB'),(325,y+35))
            draw.text((5,y+20),'Original image (thumbnail)',fill='black')
            draw.text((325,y+20),'Actual model crop (224 x 224)',fill='black')
        target=private/f'review_sheet_{page+1}.png';canvas.save(target)
        sheets.append(dict(path=str(target.relative_to(ROOT)),sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    result['visual_review_sheets']=sheets
    (out/'cases.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
