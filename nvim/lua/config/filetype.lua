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

-- Neovim's *.tf detection falls back to "tf" (TinyFugue) for empty or
-- comment-only files, and *.tofu isn't known at all. Map both to terraform
-- so tofu-ls and treesitter always apply.
vim.filetype.add({
    extension = {
        tf = "terraform",
        tofu = "terraform",
    },
})
