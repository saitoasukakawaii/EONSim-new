# EONSim Research & Learning Hub

This directory contains the public VitePress knowledge website.

## Local development

Requires Node.js 22 or newer.

```bash
cd website
npm install
npm run docs:dev
```

## Production build

```bash
npm run docs:build
npm run docs:preview
```

Build output: website/.vitepress/dist

## Cloudflare Pages configuration

Create a Cloudflare Pages project connected to this GitHub repository:

- Production branch: main
- Root directory: website
- Build command: npm run docs:build
- Build output directory: .vitepress/dist
- Node.js version: 22

Cloudflare Pages Git integration can generate preview deployments for pull requests. Production deployment occurs only from the configured production branch after a reviewed PR is merged.

No Cloudflare API token or account secret is stored in this repository.

## Content review

- Published content: learning/, knowledge/, tutorials/, development/
- Draft content: drafts/ (excluded from VitePress build)
- Codex-generated content is not published automatically.
- Promote reviewed drafts through a pull request to main.

The GitHub Actions workflow validates the VitePress production build on pull requests that change website files.


## Templates and drafts

- Article templates are stored in `templates/` and are excluded from the generated site.
- Codex-generated drafts are stored in `drafts/` and are excluded from the generated site.
- Both directories remain visible in this public GitHub repository. Never store secrets, private notes, restricted datasets, or unauthorized full-text papers there.
- Reusable knowledge capture instructions are maintained in the repository skill at `.agents/skills/eonsim-knowledge-capture/SKILL.md`.
