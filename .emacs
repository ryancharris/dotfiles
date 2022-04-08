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
  :ensure t
)

;; flycheck
(use-package flycheck
  :ensure t
  :config
  (global-flycheck-mode)
)

;; ivy
(use-package ivy
  :ensure t
  :init
  (setq ivy-use-virtual-buffers t)
  (setq enable-recursive-minibuffers t)
  :config
  (ivy-mode)
)

;; counsel
(use-package counsel
  :ensure t
)

;; company
(use-package company
  :ensure t
  :config
  (global-company-mode)
)

;; projectile
(use-package projectile
  :ensure t
  :config (projectile-mode +1)
  :init
  (setq projectile-completion-system 'ivy)
)

;; org mode
(setq org-directory "~/org/")
(setq org-support-shift-select t)

;; general
(setq show-paren-delay 0)
(setq inhibit-startup-message t)
(evil-mode 1) 
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
