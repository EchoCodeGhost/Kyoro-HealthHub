# Pull Request

## Description

[Description of the changes — 1–3 bullet points on what changed and why]

## Test plan

- [ ] ...

## Docstring changes

- [ ] New @-tags added
- [ ] Existing @-tags updated
- [ ] Medical terminology reviewed
- [ ] References added/updated
- [ ] Function docstrings added
- [ ] Examples in @usage updated

## Checklist

- [ ] All new/changed scripts have structured docstrings
- [ ] Medical terms are used correctly
- [ ] References are current and correctly cited (with DOI)
- [ ] Limitations are clearly communicated
- [ ] No medical diagnoses, gender, age, or locations included
- [ ] Code works and tests pass
- [ ] Docstring validation (`python scripts/check_docstrings.py`) passes
- [ ] Compliance check (`python scripts/check_compliance.py`) passes

## Validation results

### Before merge:
```
$ python scripts/check_docstrings.py --stats
$ python scripts/check_compliance.py --stats
```

### Docstring validation:
- [ ] All scripts have an @tier tag
- [ ] All required tags present
- [ ] Bilingual tags (@purpose.de/en, @method.de/en, @limits.de/en) present
- [ ] @refs with DOI references (if medically relevant)

### Compliance check:
- [ ] No medical diagnoses
- [ ] No gender
- [ ] No age or age range
- [ ] No locations

## AI assistants involved

<!-- Check all that contributed to this PR -->

- [ ] 🤖 Claude (Anthropic) — code review, architecture, Python/analysis scripts
- [ ] 🤖 Devstral Small / Mistral Le Chat Vibe — frontend implementation
- [ ] 🤖 Lovable — UI components & design
- [ ] 🤖 Perplexity AI — research & literature
- [ ] 🤖 Picsart AI — image editing & visual assets

---
*This template is part of the docstring quality management process.*
*Built with [Claude Code](https://claude.ai/code) · [Mistral Le Chat](https://chat.mistral.ai) · [Lovable](https://lovable.dev) · [Perplexity](https://perplexity.ai) · [Picsart](https://picsart.com)*
