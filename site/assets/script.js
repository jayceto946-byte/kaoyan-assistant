(function () {
  "use strict";

  var toggle = document.querySelector(".nav-toggle");
  var nav = document.querySelector(".site-nav");

  function setMenu(open) {
    if (!toggle) {
      return;
    }
    document.body.classList.toggle("nav-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.querySelector(".nav-toggle-label").textContent = open ? "关闭" : "菜单";
  }

  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      setMenu(toggle.getAttribute("aria-expanded") !== "true");
    });

    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) {
        setMenu(false);
      }
    });

    window.addEventListener("resize", function () {
      if (window.innerWidth > 760) {
        setMenu(false);
      }
    });
  }

  var lightbox = document.querySelector(".image-lightbox");
  var lightboxImage = document.querySelector("[data-lightbox-image]");
  var lightboxTitle = document.querySelector("#lightbox-title");
  var lightboxError = document.querySelector("[data-lightbox-error]");
  var closeButton = document.querySelector("[data-lightbox-close]");
  var previewButtons = document.querySelectorAll("[data-preview-src]");
  var lastPreviewButton = null;

  function finishClose() {
    document.body.classList.remove("lightbox-open");
    if (lightboxError) {
      lightboxError.hidden = true;
    }
    if (lastPreviewButton) {
      lastPreviewButton.focus();
    }
  }

  function closePreview() {
    if (!lightbox) {
      return;
    }
    if (typeof lightbox.close === "function" && lightbox.open) {
      lightbox.close();
    } else {
      lightbox.removeAttribute("open");
      finishClose();
    }
  }

  function openPreview(button) {
    if (!lightbox || !lightboxImage || !lightboxTitle) {
      return;
    }

    var source = button.getAttribute("data-preview-src");
    var title = button.getAttribute("data-preview-title") || "项目截图";
    if (!source) {
      return;
    }

    lastPreviewButton = button;
    lightboxTitle.textContent = title;
    lightboxImage.alt = title + "完整截图";
    lightboxImage.src = source;
    if (lightboxError) {
      lightboxError.hidden = true;
    }

    document.body.classList.add("lightbox-open");
    if (typeof lightbox.showModal === "function") {
      lightbox.showModal();
    } else {
      lightbox.setAttribute("open", "");
    }
  }

  previewButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      openPreview(button);
    });
  });

  if (lightboxImage) {
    lightboxImage.addEventListener("error", function () {
      if (lightboxError) {
        lightboxError.hidden = false;
      }
    });
  }

  if (closeButton) {
    closeButton.addEventListener("click", closePreview);
  }

  if (lightbox) {
    lightbox.addEventListener("click", function (event) {
      if (event.target === lightbox) {
        closePreview();
      }
    });
    lightbox.addEventListener("close", finishClose);
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      if (lightbox && lightbox.hasAttribute("open")) {
        closePreview();
      } else {
        setMenu(false);
        if (toggle) {
          toggle.focus();
        }
      }
    }
  });
})();