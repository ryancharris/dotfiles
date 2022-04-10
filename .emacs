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
  (setq evil-undo-system 'undo-fu))

;; set up lsp-mode
(use-package lsp-mode
  :init
  (setq lsp-keymap-prefix "C-c l")
  (setq lsp-headerline-breadcrumb-enable nil)
  :hook (
         (python-mode . lsp)
         (go-mode . lsp)
         (json-mode . lsp)
         (js2-mode . lsp)
         (make-mode . lsp)
         (markdown-mode . lsp)
         (typescript-mode . lsp)
         (terraform-mode . lsp)
         (lsp-mode . lsp-enable-which-key-integration))
  :commands lsp)
(use-package lsp-ui
  :init
  (lsp-ui-mode)
  :commands
  lsp-ui-mode
)
(use-package lsp-ivy :commands lsp-ivy-workspace-symbol)
(use-package which-key
  :init
  (which-key-mode))

;; language modes
(add-to-list 'auto-mode-alist '("\\.json\\'" . json-mode))
(add-to-list 'auto-mode-alist '("\\.tsx\\'" . typescript-mode))

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
(use-package counsel
  :config
  (counsel-mode))

;; company
(use-package company
  :bind (
    ("TAB" . company-complete-selection)
  )
  :config
  (setq company-tooltip-limit 10)
  (setq company-show-quick-access t)
  (global-company-mode)
)

;; projectile
(use-package projectile
  :init
  (projectile-mode +1)
  (setq projectile-completion-system 'ivy)
  (setq projectile-indexing-method 'hybrid)
  (setq projectile-enable-caching t)
)

;; doom modeline
(use-package doom-modeline
  :config
  (setq doom-modeline-project-detection 'projectile)
  (setq doom-modeline-major-mode-icon t)
  :hook (after-init . doom-modeline-mode))

;; icons for doom modeline
(use-package all-the-icons
  :if (display-graphic-p))

;; git & magit
(use-package git-gutter
  :init (global-git-gutter-mode +1))

(use-package magit)

;; multi cursor
(use-package multiple-cursors)

;; indent guide
(use-package indent-guide
  :hook (after-init . indent-guide-global-mode)
)

;; vterm
(use-package vterm)

;; beacon
(use-package beacon
  :init (beacon-mode 1))

;; org mode
(setq org-directory "~/org/")
(setq org-support-shift-select t)

;; general key binding groups
(use-package general)

(general-create-definer my-leader-def
  :prefix "SPC"
  "SPC" '(counsel-M-x :which-key "command")
  "TAB" '(evil-switch-to-windows-last-buffer :which-key "last buffer")
  "b" '(:ignore t :which-key "buffer")
  "c" '(:ignore t :which-key "code")
  "d" '(:ignore t :which-key "describe")
  "f" '(:ignore t :which-key "file")
  "o" '(:ignore t :which-key "open")
  "p" '(projectile-command-map :which-key "project")
  "pa" '(projectile-add-known-project :which-key "add project")
  "s" '(:ignore t :which-key "search")
  "w" '(:ignore t :which-key "window")
)

(my-leader-def
  :keymaps 'normal
  "bb" 'bs-show
  "bk" 'buffer-kill)
(my-leader-def
  :keymaps 'normal
  "cd" 'evil-goto-definition
  "c:" 'goto-line)
(my-leader-def
  :keymaps 'normal
  "da" 'counsel-apropos
  "df" 'counsel-describe-function
  "dv" 'counsel-describe-variable)
(my-leader-def
  :keymaps 'normal
  "ff" 'counsel-find-file)
(my-leader-def
  :keymaps 'normal
  "ot" 'vterm-toggle)
(my-leader-def
  :keymaps 'normal
  "s" 'swiper)
(my-leader-def
  :keymaps 'normal
  "wd" 'evil-window-delete
  "wk" 'evil-window-up
  "wj" 'evil-window-down
  "wh" 'evil-window-left
  "wl" 'evil-window-right
  "ws" 'evil-window-split
  "wv" 'evil-window-vsplit)

;; ui
(setq-default indent-tabs-mode nil)
(setq show-paren-delay 0)
(setq inhibit-startup-message t)
(load-theme 'tsdh-dark t)
(column-number-mode)
(menu-bar-mode -1)
(show-paren-mode 1)
(global-display-line-numbers-mode t)
(global-visual-line-mode t)
(delete-selection-mode +1)
(add-hook 'before-save-hook 'whitespace-cleanup)
(set-face-background 'vertical-border "gray10")
(set-face-foreground 'vertical-border (face-background 'vertical-border))

;; smooth scrolling
(setq scroll-conservatively 10000
  scroll-step 1)

;; general key bindings
(setq mac-command-modifier 'meta)
(global-set-key (kbd "≈") 'counsel-M-x)
(global-set-key (kbd "<escape>") 'keyboard-escape-quit)
(global-set-key (kbd "<escape>") 'minibuffer-keyboard-quit)

(custom-set-variables
 ;; custom-set-variables was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 '(package-selected-packages
   '(yaml-mode typescript-mode python-mode terraform-mode js2-mode vterm-toggle ## doom-modeline lsp-mode use-package projectile flycheck evil counsel company)))
(custom-set-faces
 ;; custom-set-faces was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 )
