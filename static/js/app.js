(function () {
  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function spinnerMarkup(label) {
    return (
      '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>' +
      escapeHtml(label || "Please wait...")
    );
  }

  function setLoading(button, label) {
    if (!button) {
      return;
    }
    if (!button.dataset.originalHtml) {
      button.dataset.originalHtml = button.innerHTML;
    }
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    button.innerHTML = spinnerMarkup(label || "Please wait...");
  }

  function setRedirecting(button, label) {
    setLoading(button, label || "Redirecting...");
  }

  function reset(button) {
    if (!button) {
      return;
    }
    if (button.dataset.originalHtml) {
      button.innerHTML = button.dataset.originalHtml;
    }
    button.disabled = false;
    button.removeAttribute("aria-busy");
  }

  window.aiTomato = window.aiTomato || {};
  window.aiTomato.buttonLoader = {
    setLoading: setLoading,
    setRedirecting: setRedirecting,
    reset: reset,
  };
})();

(function () {
  var toggle = document.getElementById("sidebarToggle");
  var storageKey = "aiTomatoSidebarOpen";
  var body = document.body;
  var navbar = document.querySelector(".top-navbar");
  var sidebar = document.querySelector(".sidebar-panel");
  function setSidebarState(isOpen) {
    body.classList.toggle("sidebar-open", isOpen);
    body.classList.toggle("navbar-hidden", isOpen);
    if (toggle) {
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    }
    if (navbar) {
      navbar.setAttribute("aria-hidden", isOpen ? "true" : "false");
    }
    if (sidebar) {
      sidebar.setAttribute("aria-hidden", isOpen ? "false" : "true");
    }
  }
  var stored = null;
  try {
    stored = localStorage.getItem(storageKey);
  } catch (err) {
    stored = null;
  }
  setSidebarState(stored === "true");

  if (!toggle) {
    return;
  }

  toggle.addEventListener("click", function () {
    body.classList.add("sidebar-animate");
    var isOpen = !body.classList.contains("sidebar-open");
    setSidebarState(isOpen);
    try {
      localStorage.setItem(
        storageKey,
        body.classList.contains("sidebar-open") ? "true" : "false",
      );
    } catch (err) {}
  });
})();

(function () {
  var toggles = document.querySelectorAll(".password-toggle");
  if (!toggles.length) {
    return;
  }
  toggles.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var targetId = btn.getAttribute("data-target");
      var input = null;
      if (targetId) {
        input = document.getElementById(targetId);
      }
      if (!input) {
        var group = btn.closest(".input-group");
        if (group) {
          input = group.querySelector("input");
        }
      }
      if (!input) {
        return;
      }
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.innerHTML = show
        ? '<i class="bi bi-eye-slash"></i>'
        : '<i class="bi bi-eye"></i>';
      btn.setAttribute("aria-pressed", show ? "true" : "false");
    });
  });
})();

(function () {
  function formatLocalTimes(options) {
    var opts = options || {};
    var selector = opts.selector || ".js-local-time";
    var formatter = opts.formatter;
    var keepRawOnInvalid = Boolean(opts.keepRawOnInvalid);
    var nodes = document.querySelectorAll(selector);
    if (!nodes.length) {
      return;
    }
    nodes.forEach(function (node) {
      var raw = node.getAttribute("data-time") || "";
      if (!raw) {
        node.textContent = "";
        return;
      }
      var hasTz = raw.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(raw);
      var date = new Date(hasTz ? raw : raw + "Z");
      if (isNaN(date.getTime())) {
        node.textContent = keepRawOnInvalid ? raw : "";
        return;
      }
      if (typeof formatter === "function") {
        node.textContent = formatter(date, node);
        return;
      }
      node.textContent = date.toLocaleString();
    });
  }

  function toLocalDateTime(rawValue, fallback) {
    var raw = (rawValue || "").trim();
    if (!raw) {
      return fallback || "";
    }
    var hasTz = raw.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(raw);
    var date = new Date(hasTz ? raw : raw + "Z");
    if (isNaN(date.getTime())) {
      return fallback || "";
    }
    return date.toLocaleString();
  }

  window.aiTomato = window.aiTomato || {};
  window.aiTomato.formatLocalTimes = formatLocalTimes;
  window.aiTomato.toLocalDateTime = toLocalDateTime;
})();

(function () {
  var startButton = document.getElementById("appTourStart");
  var pageMarker = document.getElementById("appTourPage");
  var currentPage = "";
  if (pageMarker) {
    currentPage = pageMarker.getAttribute("data-tour-page") || "";
  } else if (startButton) {
    currentPage = startButton.getAttribute("data-tour-page") || "";
  }
  if (!startButton && currentPage !== "index") {
    return;
  }

  var state = {
    steps: [],
    index: 0,
    previousFocus: null,
  };
  var backdrop = null;
  var highlight = null;
  var card = null;

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function findElement(selectors) {
    var list = Array.isArray(selectors) ? selectors : [selectors];
    for (var i = 0; i < list.length; i += 1) {
      try {
        var element = document.querySelector(list[i]);
        if (element && isVisible(element)) {
          return element;
        }
      } catch (err) {}
    }
    return null;
  }

  function isVisible(element) {
    if (!element) {
      return false;
    }
    var style = window.getComputedStyle(element);
    if (
      style.display === "none" ||
      style.visibility === "hidden" ||
      Number(style.opacity) === 0
    ) {
      return false;
    }
    var rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function addStep(steps, selectors, title, text) {
    var element = findElement(selectors);
    if (!element) {
      return;
    }
    steps.push({
      element: element,
      title: title,
      text: text,
    });
  }

  function buildSteps() {
    var steps = [];
    var page = currentPage;

    addStep(
      steps,
      ".top-navbar",
      "Navigation",
      "Use the top navigation to move between Home, Care Tips, About, FAQ, and account-related pages.",
    );
    addStep(
      steps,
      "#sidebarToggle",
      "Side Menu",
      "Open the side menu when you want a compact list of the main pages. Logged-in users also see Dashboard and History here.",
    );
    addStep(
      steps,
      ".nav-links",
      "Main Sections",
      "These links take you to the public information pages and support areas without returning to the home screen first.",
    );
    addStep(
      steps,
      ["#navbarSearchForm", "#headerSearchInput"],
      "Quick Page Search",
      "On the home page, type words such as history, care, feedback, or contact to jump to the matching section.",
    );

    if (page === "index") {
      addStep(
        steps,
        "#filePickerBtn",
        "Choose a Leaf Image",
        "Start a diagnosis by choosing a clear tomato leaf photo. JPG, JPEG, and PNG images are accepted.",
      );
      addStep(
        steps,
        "#detectBtn",
        "Run Detection",
        "After selecting an image, press Detect. The app checks whether it looks like a tomato leaf before sending it to the AI model.",
      );
      addStep(
        steps,
        "#resultSection",
        "Prediction Result",
        "The result area shows the predicted disease, confidence score, and a short recommendation. Logged-in scans are saved to history.",
      );
      addStep(
        steps,
        ".card-custom",
        "Care Suggestions",
        "Use these suggestion cards and the Care Tips page to review basic plant care actions after a scan.",
      );
    } else if (page === "login_page") {
      addStep(
        steps,
        "#loginForm",
        "Login Form",
        "Enter your registered email and password here. Unverified users are guided back to OTP verification.",
      );
      addStep(
        steps,
        ".password-toggle",
        "Password Visibility",
        "Use this icon when you need to check the password you typed before submitting.",
      );
      addStep(
        steps,
        "#loginSubmitBtn",
        "Submit Login",
        "The button shows a loading state while the app verifies your account.",
      );
    } else if (page === "register_page") {
      addStep(
        steps,
        "#registerForm",
        "Create Account",
        "Fill in your name, email, and password to create an account. The app then sends an OTP to verify your email.",
      );
      addStep(
        steps,
        "#otpForm",
        "Verify Email",
        "After registration, enter the OTP from your email. You can resend the code if it expires.",
      );
    } else if (page === "dashboard_page") {
      addStep(
        steps,
        ".welcome-card",
        "Dashboard Summary",
        "The dashboard gives you a quick overview after login, including shortcuts to scan and history.",
      );
      addStep(
        steps,
        ".stat-card",
        "Scan Statistics",
        "These cards summarize total scans, healthy rate, and recent disease activity.",
      );
      addStep(
        steps,
        ".section-card",
        "Recent Activity",
        "Recent scan and disease sections help you track plant health patterns over time.",
      );
    } else if (page === "history_page") {
      addStep(
        steps,
        ".history-table",
        "Scan History",
        "This table lists saved predictions with image, label, confidence, and scan time.",
      );
      addStep(
        steps,
        "#clearHistoryBtn",
        "Clear History",
        "Use this button when you want to remove all saved scans from your account.",
      );
    } else if (page === "feedback_page") {
      addStep(
        steps,
        "#feedbackForm",
        "Feedback Form",
        "Select a rating and write a short comment to share your experience with the application.",
      );
      addStep(
        steps,
        ".feedback-stars-input",
        "Star Rating",
        "Choose one to five stars. The selected value is submitted with your feedback.",
      );
      addStep(
        steps,
        "#feedbackSubmitBtn",
        "Save Feedback",
        "Submit new feedback or update your previous feedback from the same account.",
      );
    } else if (page === "contact_page") {
      addStep(
        steps,
        "form[action]",
        "Contact Support",
        "Send a subject and message from this form. Your logged-in email is used as the reply address.",
      );
    } else if (page === "account_page") {
      addStep(
        steps,
        ".profile-card",
        "Profile Details",
        "Review your account name, email address, and account creation time here.",
      );
      addStep(
        steps,
        "a[href*='change-password']",
        "Change Password",
        "Use this action when you need to update your account password.",
      );
      addStep(
        steps,
        ".danger-box",
        "Account Deletion",
        "This area contains the permanent account deletion option. Use it only when you want to remove your account and history.",
      );
    } else if (page === "change_password") {
      addStep(
        steps,
        "#passwordForm",
        "Change Password",
        "Enter your current password, then set and confirm your new password.",
      );
    } else if (page === "delete_account") {
      addStep(
        steps,
        "#confirmText",
        "Deletion Confirmation",
        'Type "DELETE" here to confirm that you understand the account deletion action.',
      );
      addStep(
        steps,
        "#deleteAccountBtn",
        "Delete Account",
        "This button removes your account, feedback, scan history, and stored scan images after password verification.",
      );
    } else if (page === "care_tips_page") {
      addStep(
        steps,
        ".tip-card",
        "Care Tip Cards",
        "Review watering, sunlight, prevention, and disease-specific care guidance here.",
      );
    } else if (page === "about_page") {
      addStep(
        steps,
        ".info-card",
        "Project Information",
        "This page explains what the system does, why it was built, and how the AI workflow operates.",
      );
    } else if (page === "faq_page") {
      addStep(
        steps,
        ".faq-card",
        "Common Questions",
        "Use this page when you need quick answers about image quality, supported diseases, or account behavior.",
      );
    } else if (page === "forgot_password_page") {
      addStep(
        steps,
        "form[action]",
        "Password Reset",
        "Enter your account email to receive a password reset link.",
      );
    } else if (
      page === "reset_password_page" ||
      page === "reset_password_query"
    ) {
      addStep(
        steps,
        "form",
        "Set New Password",
        "Enter and confirm your new password. The reset link must still be valid.",
      );
    }

    addStep(
      steps,
      [".nav-account-link", ".nav-auth-actions"],
      "Account Access",
      "Use this area to log in, sign up, or manage your account after authentication.",
    );
    addStep(
      steps,
      "#appTourStart",
      "Restart the Tour",
      "You can open this guided tour again from this button whenever you need help using the page.",
    );

    return steps;
  }

  function createTourShell() {
    backdrop = document.createElement("div");
    backdrop.className = "app-tour-backdrop";
    backdrop.setAttribute("aria-hidden", "true");

    highlight = document.createElement("div");
    highlight.className = "app-tour-highlight";
    highlight.setAttribute("aria-hidden", "true");

    card = document.createElement("div");
    card.className = "app-tour-card";
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-live", "polite");
    card.setAttribute("aria-modal", "true");

    document.body.appendChild(backdrop);
    document.body.appendChild(highlight);
    document.body.appendChild(card);
  }

  function removeTourShell() {
    [backdrop, highlight, card].forEach(function (node) {
      if (node && node.parentNode) {
        node.parentNode.removeChild(node);
      }
    });
    backdrop = null;
    highlight = null;
    card = null;
  }

  function placeCard(targetRect) {
    var spacing = 14;
    var cardWidth = Math.min(360, window.innerWidth - 32);
    var left = Math.min(
      Math.max(16, targetRect.left),
      window.innerWidth - cardWidth - 16,
    );
    var top = targetRect.bottom + spacing;

    if (top + card.offsetHeight > window.innerHeight - 16) {
      top = targetRect.top - card.offsetHeight - spacing;
    }
    if (top < 16) {
      top = 16;
    }

    card.style.left = left + "px";
    card.style.top = top + "px";
  }

  function renderStep() {
    var step = state.steps[state.index];
    if (!step) {
      endTour();
      return;
    }

    step.element.scrollIntoView({
      block: "center",
      inline: "nearest",
      behavior: "smooth",
    });

    window.setTimeout(function () {
      var rect = step.element.getBoundingClientRect();
      var padding = 8;

      highlight.style.top = Math.max(8, rect.top - padding) + "px";
      highlight.style.left = Math.max(8, rect.left - padding) + "px";
      highlight.style.width =
        Math.min(window.innerWidth - 16, rect.width + padding * 2) + "px";
      highlight.style.height =
        Math.min(window.innerHeight - 16, rect.height + padding * 2) + "px";

      var isLast = state.index === state.steps.length - 1;
      card.innerHTML =
        '<div class="app-tour-kicker"><i class="bi bi-compass"></i> Guided tour</div>' +
        '<div class="app-tour-title">' +
        escapeHtml(step.title) +
        "</div>" +
        '<div class="app-tour-text">' +
        escapeHtml(step.text) +
        "</div>" +
        '<div class="app-tour-progress">Step ' +
        (state.index + 1) +
        " of " +
        state.steps.length +
        "</div>" +
        '<div class="app-tour-actions">' +
        '<button type="button" class="btn btn-link btn-sm" data-tour-action="skip">' +
        (isLast ? "Close" : "Skip") +
        "</button>" +
        '<div class="app-tour-nav-actions">' +
        '<button type="button" class="btn btn-outline-teal btn-sm" data-tour-action="back" ' +
        (state.index === 0 ? "disabled" : "") +
        '><i class="bi bi-arrow-left"></i>Back</button>' +
        '<button type="button" class="btn btn-primary-custom btn-sm" data-tour-action="next">' +
        (isLast ? '<i class="bi bi-check2"></i>Finish' : 'Next<i class="bi bi-arrow-right"></i>') +
        "</button>" +
        "</div>" +
        "</div>";

      placeCard(rect);
      var nextButton = card.querySelector('[data-tour-action="next"]');
      if (nextButton) {
        nextButton.focus();
      }
    }, 220);
  }

  function startTour() {
    state.steps = buildSteps();
    state.index = 0;
    state.previousFocus = document.activeElement || startButton || document.body;
    if (!state.steps.length) {
      return;
    }
    document.body.classList.add("app-tour-active");
    createTourShell();
    renderStep();
  }

  function endTour() {
    document.body.classList.remove("app-tour-active");
    removeTourShell();
    if (state.previousFocus && typeof state.previousFocus.focus === "function") {
      state.previousFocus.focus();
    }
  }

  function goNext() {
    if (state.index >= state.steps.length - 1) {
      endTour();
      return;
    }
    state.index += 1;
    renderStep();
  }

  function goBack() {
    if (state.index === 0) {
      return;
    }
    state.index -= 1;
    renderStep();
  }

  if (startButton) {
    startButton.addEventListener("click", startTour);
  }

  document.addEventListener("click", function (event) {
    var actionButton = event.target.closest("[data-tour-action]");
    if (!actionButton || !card || !card.contains(actionButton)) {
      return;
    }
    var action = actionButton.getAttribute("data-tour-action");
    if (action === "next") {
      goNext();
    } else if (action === "back") {
      goBack();
    } else {
      endTour();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (!card) {
      return;
    }
    if (event.key === "Escape") {
      endTour();
    } else if (event.key === "ArrowRight") {
      goNext();
    } else if (event.key === "ArrowLeft") {
      goBack();
    }
  });

  window.addEventListener("resize", function () {
    if (card) {
      renderStep();
    }
  });

  if (currentPage === "index") {
    window.setTimeout(function () {
      var storageKey = "aiTomatoHomeTourShown";
      var alreadyShown = false;
      try {
        alreadyShown = sessionStorage.getItem(storageKey) === "true";
      } catch (err) {
        alreadyShown = false;
      }
      if (alreadyShown) {
        return;
      }
      try {
        sessionStorage.setItem(storageKey, "true");
      } catch (err) {}
      startTour();
    }, 700);
  }
})();
