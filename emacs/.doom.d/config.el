;; Profile
(setq user-full-name "Ryan Harris"
      user-mail-address "harrisryan1@gmail.com")

;; Doom UI
(setq doom-theme 'doom-gruvbox)

;; org-mode
(setq org-directory "~/org/")
(setq org-support-shift-select t)

;; org-roam
(use-package org-roam
      :ensure t
      :hook
      (after-init . org-roam-mode)
      :custom
      (org-roam-directory "~/org/")
      :bind (:map org-roam-mode-map
              (("C-c n l" . org-roam)
               ("C-c n f" . org-roam-find-file)
               ("C-c n g" . org-roam-graph-show))
              :map org-mode-map
              (("C-c n i" . org-roam-insert))
              (("C-c n I" . org-roam-insert-immediate))))

;; Text
(setq-default doom-font (font-spec :family "Fira Code" :size 18))
(setq-default display-line-numbers-type t)
(setq-default tab-width 2 )
(setq-default delete-selection-mode 1)  ; Replace selection when inserting text
(setq-default indent-tabs-mode t)
(setq-default standard-indent 2)

;; JavaScript
(require 'prettier-js)
(add-hook 'javascript-mode 'prettier-js-mode)
(add-hook 'typescript-mode 'prettier-js-mode)
(add-hook 'typescript-tsx-mode 'prettier-js-mode)

;; Enable word wrapping in all modes
(global-visual-line-mode t)

;; Key bindings
(map! :leader :desc "M-x" :n "SPC" #'counsel-M-x)  ; Spc Spc replaces Spc : to open command menu
(map! :leader "TAB" 'evil-switch-to-windows-last-buffer)  ; Spc TAB toggles to most recent buffer

;; Disable dired on mac due to lack of gls package
(when (string= system-type "darwin")
  (setq dired-use-ls-dired nil))

;; Force projectile to show all files in project
(setq projectile-indexing-method 'hybrid)
(setq projectile-completion-system 'ivy)
(setq projectile-enable-caching t)
