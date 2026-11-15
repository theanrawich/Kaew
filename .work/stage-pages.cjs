const fs = require('node:fs');
const path = require('node:path');
const root = path.dirname(__dirname);
const destination = path.join(root, '_site');
// cad-viewer.js is a generated bundle (gitignored); build it on clean checkouts.
if (!fs.existsSync(path.join(root, 'cad-viewer.js'))) require('./build-cad-viewer.cjs');
const files = [
  ['kaew-3d.html', 'index.html'],
  ['cad-viewer.html', 'cad-viewer.html'],
  ['cad-viewer.js', 'cad-viewer.js'],
  ['cad/kaew-full-assembly-20261106.zip', 'cad/kaew-full-assembly-20261106.zip'],
  ['kaew-3d.html', 'kaew-3d.html'],
  ['kaew-parts.html', 'kaew-parts.html'],
  ['pump-options.html', 'pump-options.html'],
  ['pump-options.json', 'pump-options.json'],
  ['kaew-bom.json', 'kaew-bom.json'],
  ['docs/SHOPPING_LIST.md', 'docs/SHOPPING_LIST.md'],
  ['docs/parts-verification.md', 'docs/parts-verification.md'],
];
// FreeCAD exports are optional local inputs, never required by CI.
if (fs.existsSync(path.join(root, 'cad-model.json'))) files.push(['cad-model.json', 'cad-model.json']);
fs.rmSync(destination, {recursive: true, force: true});
fs.mkdirSync(destination, {recursive: true});
for (const [source, target] of files) {
  fs.mkdirSync(path.dirname(path.join(destination, target)), {recursive: true});
  fs.copyFileSync(path.join(root, source), path.join(destination, target));
}
fs.writeFileSync(path.join(destination, '.nojekyll'), '');
console.log(JSON.stringify({directory: '_site', files: files.map(([, target]) => target)}));
