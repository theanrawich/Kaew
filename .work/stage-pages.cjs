const fs = require('node:fs');
const path = require('node:path');
const root = path.dirname(__dirname);
const destination = path.join(root, '_site');
const files = [
  ['kaew-3d.html', 'index.html'],
  ['kaew-3d.html', 'kaew-3d.html'],
  ['kaew-parts.html', 'kaew-parts.html'],
  ['kaew-bom.json', 'kaew-bom.json'],
  ['KAEW_SHOPPING_LIST.md', 'KAEW_SHOPPING_LIST.md'],
];
fs.mkdirSync(destination, { recursive: true });
for (const [source, target] of files) {
  fs.copyFileSync(path.join(root, source), path.join(destination, target));
}
fs.writeFileSync(path.join(destination, '.nojekyll'), '');
console.log(JSON.stringify({ directory: '_site', files: files.map(([, target]) => target) }));
