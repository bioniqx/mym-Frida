import { readFileSync, writeFileSync } from 'node:fs';
import JavaScriptObfuscator from 'javascript-obfuscator';

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  console.error('Usage: node obfuscate.mjs <in.js> <out.js>');
  process.exit(1);
}

const source = readFileSync(inputPath, 'utf8');

const result = JavaScriptObfuscator.obfuscate(source, {
  compact: true,
  identifierNamesGenerator: 'hexadecimal',
  renameGlobals: false,
  stringArray: true,
  stringArrayThreshold: 1,
  stringArrayEncoding: ['rc4'],
  numbersToExpressions: true,
  simplify: true,
  controlFlowFlattening: false
});

writeFileSync(outputPath, result.getObfuscatedCode(), 'utf8');
console.log(`Obfuscated ${inputPath} -> ${outputPath}`);
