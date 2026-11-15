const path = require('node:path');
const esbuild = require('./toolchain/node_modules/esbuild');
esbuild.buildSync({
  entryPoints: [path.join(__dirname, 'cad-viewer.js')],
  outfile: path.join(__dirname, '../site/cad-viewer.js'),
  bundle: true, minify: true, format: 'iife', target: 'es2020',
  nodePaths: [path.join(__dirname, 'toolchain/node_modules')],
});
