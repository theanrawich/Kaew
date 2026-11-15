const fs = require('node:fs');
const path = require('node:path');
const root = path.dirname(__dirname);
const destination = path.join(root, '_site');
// cad-viewer.js is a generated bundle (gitignored); build it on clean checkouts.
if (!fs.existsSync(path.join(root, 'site/cad-viewer.js'))) require('./build-cad-viewer.cjs');
const files = [
  ['site/kaew-3d.html', 'index.html'],
  ['site/cad-viewer.html', 'cad-viewer.html'],
  ['site/cad-viewer.js', 'cad-viewer.js'],
  ['cad/kaew-full-assembly-20261106.zip', 'cad/kaew-full-assembly-20261106.zip'],
  ['site/kaew-3d.html', 'kaew-3d.html'],
  ['site/kaew-parts.html', 'kaew-parts.html'],
  ['docs/kaew-bom.json', 'kaew-bom.json'],
  ['docs/SHOPPING_LIST.md', 'docs/SHOPPING_LIST.md'],
  ['docs/parts-verification.md', 'docs/parts-verification.md'],
];
// FreeCAD exports are optional local inputs, never required by CI.
if (fs.existsSync(path.join(root, 'site/cad-model.json'))) files.push(['site/cad-model.json', 'cad-model.json']);
fs.rmSync(destination, {recursive: true, force: true});
fs.mkdirSync(destination, {recursive: true});
for (const [source, target] of files) {
  fs.mkdirSync(path.dirname(path.join(destination, target)), {recursive: true});
  // Source pages live one level deeper locally; published URLs stay at the root.
  if (source === 'site/cad-viewer.html') {
    const html = fs.readFileSync(path.join(root, source), 'utf8')
      .replace('href="kaew-3d.html"', 'href="index.html"')
      .replaceAll('href="../cad/', 'href="cad/');
    fs.writeFileSync(path.join(destination, target), html);
  } else if (source === 'docs/parts-verification.md') {
    const markdown = fs.readFileSync(path.join(root, source), 'utf8')
      .replaceAll('`docs/kaew-bom.json`', '`kaew-bom.json`');
    fs.writeFileSync(path.join(destination, target), markdown);
  } else {
    fs.copyFileSync(path.join(root, source), path.join(destination, target));
  }
}
fs.writeFileSync(path.join(destination, '.nojekyll'), '');
console.log(JSON.stringify({directory: '_site', files: files.map(([, target]) => target)}));
