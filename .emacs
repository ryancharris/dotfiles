;; set up package.el to work with MELPA
(require 'package)
(add-to-list 'package-archives '("melpa" . "https://melpa.org/packages/") t)
(package-initialize)

;; set up evil-mode
(unless (package-installed-p 'evil)
  (package-install 'evil))

(evil-mode 1)
(define-key evil-normal-state-map (kbd "SPC SPC") 'counsel-M-x)

;; file keybindings
(define-key evil-normal-state-map (kbd "SPC f f") 'counsel-find-file)

;; buffer keybindings
(define-key evil-normal-state-map
    (kbd "SPC TAB") 'evil-switch-to-windows-last-buffer
)
(define-key evil-normal-state-map
    (kbd "SPC b b") 'bs-show
)
(define-key evil-normal-state-map
    (kbd "SPC b k") 'kill-current-buffer
)

;; window keybindings
(define-key evil-normal-state-map
    (kbd "SPC w k") 'evil-window-delete
)
(define-key evil-normal-state-map
    (kbd "SPC w s") 'evil-window-split
)
(define-key evil-normal-state-map
    (kbd "SPC w v") 'evil-window-vsplit
)

;; ivy
(ivy-mode)
(setq ivy-use-virtual-buffers t)
(setq enable-recursive-minibuffers t)
(define-key minibuffer-local-map (kbd "C-r") 'counsel-minibuffer-history)

;; projectile
(projectile-mode +1)
(setq projectile-completion-system 'ivy)

;; org mode
(setq org-directory "~/org/")
(setq org-support-shift-select t)

;; general
(load-theme 'gruvbox-dark-hard t)
(menu-bar-mode -1)
(show-paren-mode 1)
(setq show-paren-delay 0)
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

;; set packages
(custom-set-variables
 ;; custom-set-variables was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 '(custom-safe-themes
   '("d14f3df28603e9517eb8fb7518b662d653b25b26e83bd8e129acea042b774298" "af8ca9d93f5a0df7f522c72bf939c108427ef7b66abc43f7979b3b48aafbcb2a" "78e6be576f4a526d212d5f9a8798e5706990216e9be10174e3f3b015b8662e27" default))
 '(package-selected-packages
   '(gruvbox-theme multiple-cursors projectile counsel ivy evil)))

 ;; set custom faces
(custom-set-faces
 ;; custom-set-faces was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 )
