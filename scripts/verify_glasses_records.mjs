// Cross-language contract check: consume JSON actually emitted by the Kotlin JVM tests.
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {validateCaptureEvent,validateFinding} from '../deploy/onboarding/platform/validators.mjs';
const input=process.argv[2]??'android-companion/app/build/glasses-fixtures';
const rows=[['capture.json',validateCaptureEvent],['finding.json',validateFinding]].map(([file,validate])=>{
  const document=JSON.parse(readFileSync(`${input}/${file}`,'utf8'));
  const passed=validate(document);
  return {file,schemaVersion:document.schemaVersion,passed,errors:validate.errors??[]};
});
mkdirSync('artifacts/glasses',{recursive:true});
writeFileSync('artifacts/glasses/schema-check.json',JSON.stringify({date:new Date().toISOString(),rows},null,2));
console.log(JSON.stringify(rows));
if(rows.some(row=>!row.passed))process.exitCode=1;
