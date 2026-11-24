import fs from 'node:fs'
import path from 'node:path'
const root = path.resolve(import.meta.dirname, '../..')
const sourceOnly = process.argv.includes('--source-only')
const walk = (dir) => fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)])
const files = [path.join(root, 'AGENTS.md'), ...['CODEX_PROGRESS', 'CODEX_TASK_QUEUE', 'CODEX_SESSION_LOG'].map(n => path.join(root, `docs/development/${n}.md`)), ...walk(path.join(root, 'website/templates')), path.join(root, 'website/development/contribution.md'), path.join(root, 'website/README.md')]
let errors = []
for (const file of files) {
  // Git may check out CRLF on Windows; validate the normalized Markdown.
  const text = fs.readFileSync(file, 'utf8').replace(/\r\n/g, '\n')
  if (!text.endsWith('\n') || /\r/.test(text)) errors.push(`${file}: require LF/CRLF and final newline`)
  if (text.split('\n').some(l => /\s+$/.test(l))) errors.push(`${file}: trailing whitespace`)
  if ((text.match(/^```/gm) || []).length % 2) errors.push(`${file}: unclosed fence`)
  if (!/^# /m.test(text)) errors.push(`${file}: missing title`)
  for (const m of text.matchAll(/\]\(([^)]+)\)/g)) {
    const link = m[1].split('#')[0]
    if (link && !/^(https?:|mailto:|\/)/.test(link) && !fs.existsSync(path.resolve(path.dirname(file), link))) errors.push(`${file}: missing ${link}`)
  }
}
const dist = path.join(root, 'website/.vitepress/dist')
if (!sourceOnly && !fs.existsSync(dist)) errors.push('Build website before checking output isolation')
else if (!sourceOnly) for (const file of walk(dist)) {
  const relative = path.relative(dist, file)
  if (/^(drafts|templates)[/\\]/.test(relative)) errors.push(`Excluded output: ${relative}`)
  if (/\.(html|js|json)$/.test(file) && /EONSIM_PRIVATE_(DRAFT|TEMPLATE)_SENTINEL_20261030/.test(fs.readFileSync(file, 'utf8'))) errors.push(`Unpublished content leaked into ${relative}`)
}
// The Markdown plugin can parse TeX while Vue drops the generated math elements
// from server-rendered pages. Check the actual production HTML as well.
if (!sourceOnly && fs.existsSync(dist)) {
  for (const page of ['knowledge/monolithic-fsi', 'knowledge/tet4-viscosity']) {
    const file = path.join(dist, page + '.html')
    const html = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : ''
    if (!/<mjx-container\b[^>]*>\s*<svg\b/.test(html) || html.includes('data-mml-node="merror"')) {
      errors.push(`${page}: expected a rendered MathJax SVG without TeX errors`)
    }
  }
}
if (errors.length) { console.error(errors.join('\n')); process.exit(1) }
console.log(`Markdown structure and local links: ${files.length} files passed; ${sourceOnly ? 'production isolation NOT checked (source-only)' : 'production draft/template isolation passed'}.`)
