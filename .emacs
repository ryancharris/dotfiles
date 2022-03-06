;; set up package.el to work with MELPA
(require 'package)
(add-to-list 'package-archives '("melpa" . "https://melpa.org/packages/") t)
(package-initialize)

;; set up evil-mode
(unless (package-installed-p 'evil)
  (package-install 'evil))

(evil-mode 1)
(define-key evil-normal-state-map (kbd "SPC SPC") 'counsel-M-x)
(define-key evil-normal-state-map (kbd "SPC f f") 'find-file)
(define-key evil-normal-state-map
    (kbd "SPC TAB") 'evil-switch-to-windows-last-buffer
)
(define-key evil-normal-state-map
    (kbd "SPC b b") 'bs-show
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
(menu-bar-mode -1)
(show-paren-mode 1)
(setq show-paren-delay 0)
(global-display-line-numbers-mode t)
(global-visual-line-mode t)

;; set packages
(custom-set-variables
 ;; custom-set-variables was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 '(custom-safe-themes
   '("78e6be576f4a526d212d5f9a8798e5706990216e9be10174e3f3b015b8662e27" default))
 '(package-selected-packages '(monokai-theme projectile counsel ivy evil)))

 ;; set custom faces
(custom-set-faces
 ;; custom-set-faces was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 )
