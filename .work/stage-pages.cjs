const fs = require('node:fs');
const path = require('node:path');
const root = path.dirname(__dirname);
const destination = path.join(root, '_site');
const files = [
  ['cad-viewer.html', 'index.html'],
  ['cad-viewer.js', 'cad-viewer.js'],
  ['cad-model.json', 'cad-model.json'],
  ['cad/kaew-full-assembly-20261106.zip', 'cad/kaew-full-assembly-20261106.zip'],
  ['kaew-3d.html', 'kaew-3d.html'],
  ['kaew-parts.html', 'kaew-parts.html'],
  ['pump-options.html', 'pump-options.html'],
  ['pump-options.json', 'pump-options.json'],
  ['kaew-bom.json', 'kaew-bom.json'],
  ['KAEW_SHOPPING_LIST.md', 'KAEW_SHOPPING_LIST.md'],
];
fs.mkdirSync(destination, { recursive: true });
for (const [source, target] of files) {
  fs.mkdirSync(path.dirname(path.join(destination, target)), { recursive: true });
  fs.copyFileSync(path.join(root, source), path.join(destination, target));
}
fs.writeFileSync(path.join(destination, '.nojekyll'), '');
console.log(JSON.stringify({ directory: '_site', files: files.map(([, target]) => target) }));
