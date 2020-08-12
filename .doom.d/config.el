;;; $DOOMDIR/config.el -*- lexical-binding: t; -*-

;; Place your private configuration here! Remember, you do not need to run 'doom
;; sync' after modifying this file!


;; Some functionality uses this to identify you, e.g. GPG configuration, email
;; clients, file templates and snippets.
(setq user-full-name "Ryan Harris"
      user-mail-address "harrisryan1@gmail.com")

;; Doom exposes five (optional) variables for controlling fonts in Doom. Here
;; are the three important ones:
;;
;; + `doom-font'
;; + `doom-variable-pitch-font'
;; + `doom-big-font' -- used for `doom-big-font-mode'; use this for
;;   presentations or streaming.
;;
;; They all accept either a font-spec, font string ("Input Mono-12"), or xlfd
;; font string. You generally only need these two:
(setq doom-font (font-spec :family "Fira Code" :size 18))

;; There are two ways to load a theme. Both assume the theme is installed and
;; available. You can either set `doom-theme' or manually load a theme with the
;; `load-theme' function. This is the default:
(load-theme 'doom-dracula t)

;; If you use `org' and don't want your org files in the default location below,
;; change `org-directory'. It must be set before org loads!
(setq org-directory "~/org/")

;; This determines the style of line numbers in effect. If set to `nil', line
;; numbers are disabled. For relative line numbers, set this to `relative'.
(setq display-line-numbers-type t)

;; Set defaults for text editing
(setq-default tab-width 2 )
(setq-default delete-selection-mode 1)         ; Replace selection when inserting text


;; Here are some additional functions/macros that could help you configure Doom:
;;
;; - `load!' for loading external *.el files relative to this one
;; - `use-package' for configuring packages
;; - `after!' for running code after a package has loaded
;; - `add-load-path!' for adding directories to the `load-path', relative to
;;   this file. Emacs searches the `load-path' when you load packages with
;;   `require' or `use-package'.
;; - `map!' for binding new keys
;;
;; To get information about any of these functions/macros, move the cursor over
;; the highlighted symbol at press 'K' (non-evil users must press 'C-c g k').
;; This will open documentation for it, including demos of how they are used.
;;
;; You can also try 'gd' (or 'C-c g d') to jump to their definition and see how
;; they are implemented.

;; Spc Spc replaces Spc : to open command menu
(map! :leader
      :desc "Open like spacemacs" "SPC" #'counsel-M-x)

;; Spc TAB toggles to most recent buffer
(map! :leader "TAB" 'evil-switch-to-windows-last-buffer)

;; Treemacs always shows project of currently opened file
(setq
 treemacs-follow-mode t
 treemacs-indentation 1
 treemacs-width 25
)

;; Add Prettier configuration
(require 'prettier-js)
(add-hook 'javascript-mode 'prettier-js-mode)
(add-hook 'typescript-mode 'prettier-js-mode)


;; Set initial Doom frame size
(setq initial-frame-alist '((width . 175) (height . 40)))

;; Add shift selection in org mode
(setq org-support-shift-select t)
