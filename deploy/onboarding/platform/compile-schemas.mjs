import Ajv from 'ajv';
import standalone from 'ajv/dist/standalone/index.js';
import {mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {schemas} from './schema-spec.mjs';
const here=path.dirname(fileURLToPath(import.meta.url)),folder=path.join(here,'schemas');
await mkdir(folder,{recursive:true});
const ajv=new Ajv({strict:true,allowUnionTypes:true,code:{source:true,esm:true}}),exports={};
for(const [name,schema]of Object.entries(schemas)){await writeFile(path.join(folder,`${name}.v1.json`),JSON.stringify(schema,null,2));ajv.addSchema(schema);exports[`validate${name}`]=schema.$id;}
const code=standalone(ajv,exports).replaceAll('require("ajv/dist/runtime/ucs2length").default','((value)=>Array.from(value).length)');
if(code.includes('require('))throw Error('Unexpected non-browser runtime helper in compiled schemas');
await writeFile(path.join(here,'validators.mjs'),code);
console.log(`Compiled ${Object.keys(schemas).length} v1 JSON Schema contracts`);
