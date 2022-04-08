;; make sure we have use-package
(when (not (package-installed-p 'use-package))
  (package-refresh-contents)
  (package-install 'use-package)
)

;; set up package.el to work with ELPA & MELPA
(require 'package)
(setq package-archives '(("melpa" . "https://melpa.org/packages/")
                         ("elpa" . "https://elpa.gnu.org/packages/")))
(package-initialize)
(unless package-archive-contents
  (package-refresh-contents))

;; set up use-package
(require 'use-package)
(setq use-package-always-ensure t)
(setq use-package-always-defer t)
(setq use-package-verbose t)

;; set up evil-mode
(use-package evil
  :init
  (evil-mode 1) 
)

;; set up lsp-mode
(use-package lsp-mode
  :init
  (setq lsp-keymap-prefix "C-c l")
  :hook (
         (python-mode . lsp)
         (go-mode . lsp)
         (json-mode . lsp)
         (js2-mode . lsp)
         (make-mode . lsp)
         (terraform-mode . lsp)
         (lsp-mode . lsp-enable-which-key-integration))
  :commands lsp)
(use-package lsp-ui :commands lsp-ui-mode)
(use-package lsp-ivy :commands lsp-ivy-workspace-symbol)

;; set up debugger
(use-package dap-mode)

;; flycheck
(use-package flycheck
  :config
  (global-flycheck-mode)
)

;; ivy
(use-package ivy
  :init
  (setq ivy-use-virtual-buffers t)
  (setq enable-recursive-minibuffers t)
  :config
  (ivy-mode)
)

;; counsel
(use-package counsel)

;; company
(use-package company
  :config
  (global-company-mode t)
)

;; projectile
(use-package projectile
  :config (projectile-mode +1)
  :init
  (setq projectile-completion-system 'ivy)
)

;; doom modeline
(use-package doom-modeline
  :hook (after-init . doom-modeline-mode))

;; magit
(use-package magit)

;; org mode
(setq org-directory "~/org/")
(setq org-support-shift-select t)

;; general
(setq show-paren-delay 0)
(setq inhibit-startup-message t)
(column-number-mode)
(menu-bar-mode -1)
(show-paren-mode 1)
(global-display-line-numbers-mode t)
(global-visual-line-mode t)

;; mac os keybindings
(setq mac-command-modifier 'meta)
(global-set-key (kbd "M-c") 'kill-ring-save) ; ⌘-c = Copy
(global-set-key (kbd "M-x") 'kill-region) ; ⌘-x = Cut
(global-set-key (kbd "M-v") 'yank) ; ⌘-v = Paste
(global-set-key (kbd "M-a") 'mark-whole-buffer) ; ⌘-a = Select all
(global-set-key (kbd "M-z") 'undo) ; ⌘-z = Undo
(global-set-key (kbd "≈") 'execute-extended-command) ; Replace ≈ with whatever your option-x produces

(custom-set-variables
 ;; custom-set-variables was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 '(package-selected-packages
   '(doom-modeline lsp-mode use-package projectile flycheck evil counsel company)))
(custom-set-faces
 ;; custom-set-faces was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 )
