return {
    {
        "pmizio/typescript-tools.nvim",
        dependencies = { "nvim-lua/plenary.nvim", "neovim/nvim-lspconfig" },
        opts = {},
    },
    {
        "neovim/nvim-lspconfig",
        dependencies = {
            "williamboman/mason.nvim",
            "williamboman/mason-lspconfig.nvim",
            "b0o/schemastore.nvim",
        },
        config = function()
            require("mason").setup()

            local servers = {
                "bashls", "cssls", "dockerls", "eslint", "gopls",
                "helm_ls", "html", "jsonls", "pyright", "rust_analyzer",
                "tofu_ls", "yamlls"
            }

            require("mason-lspconfig").setup({
                ensure_installed = servers,
            })

            -- Setup completion capabilities if available
            local capabilities = {}
            local has_cmp, cmp_lsp = pcall(require, "cmp_nvim_lsp")
            if has_cmp then
                capabilities = cmp_lsp.default_capabilities()
            end

            -- Set global defaults for all LSP servers
            vim.lsp.config("*", { capabilities = capabilities })

            -- Configure and enable servers using the new Neovim 0.11+ API
            local has_schemastore, schemastore = pcall(require, "schemastore")

            for _, server in ipairs(servers) do
                local opts = {}
                if server == "eslint" then
                    opts.filetypes = { "javascript", "javascriptreact", "javascript.jsx", "typescript", "typescriptreact", "typescript.tsx", "vue", "svelte", "astro" }
                elseif server == "yamlls" and has_schemastore then
                    -- Helm templates are detected as filetype "helm" (config/filetype.lua)
                    -- and served by helm_ls instead, so yamlls only ever sees real YAML.
                    opts.settings = {
                        yaml = {
                            schemaStore = { enable = false, url = "" },
                            schemas = schemastore.yaml.schemas(),
                        },
                    }
                end
                vim.lsp.config(server, opts)
            end

            vim.lsp.enable(servers)

            -- Format on save for Go (gopls: organize imports + gofmt) and OpenTofu (tofu-ls: tofu fmt)
            local format_on_save = { gopls = true, tofu_ls = true }
            local group = vim.api.nvim_create_augroup("lsp_format_on_save", { clear = true })

            local function organize_imports(bufnr, client)
                local params = vim.lsp.util.make_range_params(0, client.offset_encoding)
                params.context = { only = { "source.organizeImports" }, diagnostics = {} }
                local res = client:request_sync("textDocument/codeAction", params, 1000, bufnr)
                for _, action in ipairs((res and res.result) or {}) do
                    if action.edit then
                        vim.lsp.util.apply_workspace_edit(action.edit, client.offset_encoding)
                    end
                end
            end

            vim.api.nvim_create_autocmd("LspAttach", {
                group = group,
                callback = function(args)
                    local client = vim.lsp.get_client_by_id(args.data.client_id)
                    if not client or not format_on_save[client.name] then
                        return
                    end
                    vim.api.nvim_create_autocmd("BufWritePre", {
                        group = group,
                        buffer = args.buf,
                        callback = function()
                            if client.name == "gopls" then
                                organize_imports(args.buf, client)
                            end
                            vim.lsp.buf.format({ bufnr = args.buf, id = client.id, timeout_ms = 2000 })
                        end,
                    })
                end,
            })
        end,
    },
}
