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

;; make sure we have use-package
(when (not (package-installed-p 'use-package))
  (package-refresh-contents)
  (package-install 'use-package)
)

;; catppuccin-theme
(use-package catppuccin-theme)
(load-theme 'catppuccin :no-confirm)

;; set up evil-mode
(use-package evil
  :init
  (evil-mode 1)
  (setq evil-undo-system 'undo-fu))

(use-package eglot
  :init
  (add-hook 'prog-mode-hook 'eglot-ensure)
)

(use-package which-key
  :init
  (which-key-mode))

;; language modes
(use-package json-mode)

(use-package typescript-mode
  :init
  (add-hook 'typescript-mode-hook (
            lambda ()
                    (setq indent-tabs-mode f)
                    (setq tab-width 2)))
)
(use-package prettier-js
  :init
  (add-hook 'javascript-mode 'prettier-js-mode)
  (add-hook 'typescript-mode 'prettier-js-mode)
)

(use-package go-mode
  :init
  (setq tab-width 2))


(add-to-list 'auto-mode-alist '("\\.json\\'" . json-mode))
(add-to-list 'auto-mode-alist '("\\.jsx\\'" . javascript-mode))
(add-to-list 'auto-mode-alist '("\\.tsx\\'" . typescript-mode))

;; python
(use-package python-black
  :demand t
  :after python
  :hook (python-mode . python-black-on-save-mode-enable-dwim))

;; solidity
(use-package company-solidity)
(use-package solidity-mode)
(use-package solidity-flycheck
  :init
  (setq solidity-flycheck-solium-checker-active t))
(add-to-list 'auto-mode-alist '("\\.sol\\'" . solidity-mode))

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
  (setq company-minimum-prefix-length 1
      company-idle-delay 0.0)
  (global-company-mode)
)

;; ag
(use-package ag
  :config
  (setq ag-highlight-search t)
  (setq ag-reuse-buffers 't)
)

;; projectile
(use-package projectile
  :init
  (projectile-mode +1)
  (setq projectile-completion-system 'ivy)
  (setq projectile-indexing-method 'hybrid)
  (setq projectile-enable-caching t)
)

;; icons for doom modeline
(require 'nerd-icons)

;; doom modeline
(use-package doom-modeline
  :config
  (setq doom-modeline-project-detection 'projectile)
  (setq doom-modeline-major-mode-icon t)
  :hook (after-init . doom-modeline-mode))

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
  "m" '(:ignore t :which-key "magit")
  "p" '(projectile-command-map :which-key "project")
  "pa" '(projectile-add-known-project :which-key "add project")
  "pr" '(projectile-remove-known-project :which-key "remove project")
  "ps" '(projectile-ag :which-key "search project")
  "w" '(:ignore t :which-key "window")
  "s" '(swiper-thing-at-point :which-key "search")
  "u" '(:ignore t :which-key "undo")
)

(my-leader-def
  :keymaps 'normal
  "bb" 'counsel-switch-buffer
  "bk" 'kill-buffer)
(my-leader-def
  :keymaps 'normal
  "cd" 'xref-find-definitions
  "cr" 'xref-find-references
  "c:" 'goto-line)
(my-leader-def
  :keymaps 'normal
  "da" 'counsel-apropos
  "df" 'counsel-describe-function
  "dv" 'counsel-describe-variable)
(my-leader-def
  :keymaps 'normal
  "fc" 'dired-create-empty-file
  "ff" 'counsel-find-file)
(my-leader-def
  :keymaps 'normal
  "mb" 'magit-blame
  "ms" 'magit-status)
(my-leader-def
  :keymaps 'normal
  "wd" 'evil-window-delete
  "wk" 'evil-window-up
  "wj" 'evil-window-down
  "wh" 'evil-window-left
  "wl" 'evil-window-right
  "ws" 'evil-window-split
  "wv" 'evil-window-vsplit)
(my-leader-def
  :keymaps 'normal
  "ur" 'undo-redo
  "uu" 'undo-only)

;; ui
(setq-default indent-tabs-mode nil)
(setq show-paren-delay 0)
(setq inhibit-startup-message t)
(setq visible-bell t)
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
   '(eglot json-mode ag yaml-mode typescript-mode python-mode terraform-mode js2-mode vterm-toggle ## use-package projectile flycheck evil counsel company)))
(custom-set-faces
 ;; custom-set-faces was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 )
