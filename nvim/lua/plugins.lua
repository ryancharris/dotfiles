vim.cmd([[
  augroup packer_user_config
    autocmd!
    autocmd BufWritePost plugins.lua source <afile> | PackerCompile
  augroup end
]])
vim.cmd [[colorscheme tokyonight-moon]]

return require('packer').startup(function(use)
    use 'wbthomason/packer.nvim'
    use {
        "williamboman/mason.nvim",
        config = function()
            require("mason").setup()
        end
    }
    use {
      'nvim-lualine/lualine.nvim',
      requires = { 'kyazdani42/nvim-web-devicons', opt = true }
    }
    use "nvim-lua/plenary.nvim"
    use {
      'nvim-telescope/telescope.nvim', tag = '0.1.1',
      requires = { {'nvim-lua/plenary.nvim'} }
    }
    use 'folke/tokyonight.nvim'
    use {
      "ahmedkhalf/project.nvim",
      config = function()
          require('telescope').load_extension('projects')
          require'telescope'.extensions.projects.projects{}

        require("project_nvim").setup {
        }
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
    use {'akinsho/bufferline.nvim', tag = "v3.*", requires = 'nvim-tree/nvim-web-devicons'}
    use {
      'lewis6991/gitsigns.nvim',
      config = function()
        require('gitsigns').setup()
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
            require'lspconfig'.eslint.setup{}
            require'lspconfig'.html.setup{}
        end
    }
    use {"akinsho/toggleterm.nvim", tag = '*', config = function()
          require("toggleterm").setup()
        end
    }
    use {
      'nvim-lualine/lualine.nvim',
      requires = { 'kyazdani42/nvim-web-devicons', opt = true }
    }
    use {
        "lukas-reineke/indent-blankline.nvim",
        config = function()
            require("indent_blankline").setup{} 
        end
    }
end)
