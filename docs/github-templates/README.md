# GitHub templates

These files belong in a `.github/` folder at the repository root:

```
.github/ISSUE_TEMPLATE/bug_report.yml
.github/ISSUE_TEMPLATE/config.yml
.github/ISSUE_TEMPLATE/feature_request.yml
.github/pull_request_template.md
```

They are stored here because the tool that prepared this repository was not allowed to write into `.github/`. Move them with:

```sh
mkdir -p .github && mv docs/github-templates/ISSUE_TEMPLATE docs/github-templates/pull_request_template.md .github/ && rm -r docs/github-templates
```
