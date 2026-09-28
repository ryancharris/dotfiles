-- Helm chart templates aren't valid YAML (Go template syntax like `{{- if }}`
-- breaks yamlls's parser and floods every line with cascading diagnostics),
-- so detect them as their own filetype and let helm-ls handle them instead.
vim.filetype.add({
    pattern = {
        [".*/templates/.*%.yaml"] = "helm",
        [".*/templates/.*%.tpl"] = "helm",
        [".*/templates/.*%.yml"] = "helm",
        ["helmfile.*%.yaml"] = "helm",
    },
})
