vim.cmd([[
  augroup packer_user_config
    autocmd!
    autocmd BufWritePost plugins.lua source <afile> | PackerCompile
  augroup end
]])

return require('packer').startup(function(use)
    use 'wbthomason/packer.nvim'
    use { "catppuccin/nvim", as = "catppuccin" }
    use {
        "williamboman/mason.nvim",
        config = function()
            require("mason").setup()
        end
    }
    use {
        "windwp/nvim-autopairs",
        config = function() require("nvim-autopairs").setup {} end
    }
    use {
        'numToStr/Comment.nvim',
        config = function()
            require('Comment').setup()
        end
    }
    use 'nvim-tree/nvim-web-devicons'
    use {
      'nvim-lualine/lualine.nvim',
      requires = { 'kyazdani42/nvim-web-devicons', opt = true },
      config = function()
          require ("lualine").setup{
              options = { section_separators = '', component_separators = '' },
              sections = {
                  lualine_a = {
                      {
                          'mode',
                          fmt = function(str) return str:sub(1,1) end
                      }
                  },
                  lualine_c = {
                      {
                          'filename',
                          path = 1,
                      }
                  },
                  lualine_x = {'filetype'},
                  lualine_y = {},
              }

          }
      end
    }
    use {
      'lewis6991/gitsigns.nvim',
      config = function()
        require('gitsigns').setup{
            current_line_blame = true,
        }
      end
    }
    use {
        'neovim/nvim-lspconfig',
        config = function()
            require'lspconfig'.pyright.setup{}
            require'lspconfig'.yamlls.setup{}
            require'lspconfig'.bashls.setup{}
            require'lspconfig'.dockerls.setup{}
            require'lspconfig'.gopls.setup{}
            require'lspconfig'.jsonls.setup{}
            require'lspconfig'.cssls.setup{}
            require'lspconfig'.eslint.setup{
                filetypes = {"javascript", "javascriptreact", "javascript.jsx", "vue", "svelte", "astro"}
            }
            require'lspconfig'.html.setup{}
            require'lspconfig'.ts_ls.setup{
                on_attach = function(client, bufnr)
                    client.server_capabilities.documentFormattingProvider = false
                end,
                filetypes = {"typescript", "typescriptreact", "typescript.tsx"}
            }
        end
    }
    use "lukas-reineke/indent-blankline.nvim"
end)
