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

-- Neovim maps *.tf to "tf" (TinyFugue) by default, so terraform/OpenTofu
-- language servers never attach. Treat OpenTofu sources as terraform.
vim.filetype.add({
    extension = {
        tf = "terraform",
        tofu = "terraform",
    },
})
