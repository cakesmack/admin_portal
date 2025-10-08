// script.js - All reusable utility functions in ONE file

// ==================== PRODUCT CODE UTILITIES ====================

export function extractProductCode(description) {
  if (!description) return "";
  const match = description.match(/\[([^\]]+)\]/);
  return match ? match[1] : "";
}

export function formatProductWithCode(product) {
  if (!product) return "";
  return product.code ? `${product.name} [${product.code}]` : product.name;
}

export function parseProductString(productString) {
  if (!productString) return { name: "", code: "" };

  const match = productString.match(/^(.+?)\s*\[([^\]]+)\]$/);
  if (match) {
    return { name: match[1].trim(), code: match[2].trim() };
  }
  return { name: productString.trim(), code: "" };
}

// ==================== DATE UTILITIES ====================

export function getMondayOfWeek(date = new Date()) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(d.setDate(diff));
}

export function formatDate(date) {
  const d = new Date(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function formatDateDisplay(date) {
  const d = new Date(date);
  const day = String(d.getDate()).padStart(2, "0");
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const year = d.getFullYear();
  return `${day}/${month}/${year}`;
}

export function getWeekNumber(date) {
  const d = new Date(
    Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())
  );
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d - yearStart) / 86400000 + 1) / 7);
}

export function getWeekIdentifier(date = new Date()) {
  const monday = getMondayOfWeek(date);
  const weekNum = getWeekNumber(monday);
  return `${monday.getFullYear()}-W${String(weekNum).padStart(2, "0")}`;
}

// ==================== GENERAL UTILITIES ====================

export function generateUniqueId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

export function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

export function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

export function formatCurrency(value, currency = "£") {
  return `${currency}${parseFloat(value).toFixed(2)}`;
}

export function safeParseFloat(value, defaultValue = 0) {
  const parsed = parseFloat(value);
  return isNaN(parsed) ? defaultValue : parsed;
}

export function capitalizeWords(str) {
  if (!str) return "";
  return str
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

// ==================== CUSTOMER SEARCH & DROPDOWN (API-BASED) ====================

/**
 * Setup customer search autocomplete on input fields
 * @param {string} accountInputId - ID of account number input
 * @param {string} nameInputId - ID of customer name input
 * @param {Function} onSelect - Optional callback when customer is selected
 */
export function setupCustomerSearch(accountInputId = "customerAccount", nameInputId = "customerName", onSelect = null) {
  const accountInput = document.getElementById(accountInputId);
  const nameInput = document.getElementById(nameInputId);

  if (accountInput) {
    accountInput.addEventListener("input", function(e) {
      const value = e.target.value;
      clearTimeout(accountInput._searchTimeout);
      
      if (value.length >= 2) {
        accountInput._searchTimeout = setTimeout(() => {
          searchCustomersAPI(value, "account", onSelect);
        }, 300);
      } else {
        hideCustomerDropdown();
      }
    });
  }

  if (nameInput) {
    nameInput.addEventListener("input", function(e) {
      const value = e.target.value;
      clearTimeout(nameInput._searchTimeout);
      
      if (value.length >= 2) {
        nameInput._searchTimeout = setTimeout(() => {
          searchCustomersAPI(value, "name", onSelect);
        }, 300);
      } else {
        hideCustomerDropdown();
      }
    });
  }

  document.addEventListener("click", function (e) {
    if (!e.target.closest(".search-container")) {
      hideCustomerDropdown();
    }
  });
}

/**
 * Search customers via API
 */
export async function searchCustomersAPI(query, searchType, onSelect = null) {
  try {
    const response = await fetch(
      `/api/customers/search?q=${encodeURIComponent(query)}`
    );
    const customers = await response.json();

    if (customers.length > 0) {
      showCustomerDropdown(customers, searchType, onSelect);
    } else {
      hideCustomerDropdown();
    }
  } catch (error) {
    console.error("Error searching customers:", error);
  }
}

/**
 * Display customer search dropdown
 */
export function showCustomerDropdown(customers, searchType, onSelect = null) {
  hideCustomerDropdown();

  const targetInput =
    searchType === "account"
      ? document.getElementById("customerAccount")
      : document.getElementById("customerName");

  if (!targetInput) return;

  const container = targetInput.parentElement;

  const dropdown = document.createElement("div");
  dropdown.className = "dropdown-results";
  dropdown.style.position = "absolute";
  dropdown.style.top = "100%";
  dropdown.style.left = "0";
  dropdown.style.right = "0";
  dropdown.style.zIndex = "1000";
  dropdown.style.maxHeight = "300px";
  dropdown.style.overflowY = "auto";
  dropdown.style.backgroundColor = "white";
  dropdown.style.border = "1px solid #ddd";
  dropdown.style.borderRadius = "4px";
  dropdown.style.boxShadow = "0 2px 4px rgba(0,0,0,0.1)";

  customers.forEach((customer) => {
    const item = document.createElement("div");
    item.className = "dropdown-item";
    item.style.padding = "10px";
    item.style.cursor = "pointer";
    item.innerHTML = `
      <strong>${customer.name}</strong>
      <div style="font-size: 0.85em; color: #666;">
        Account: ${customer.account_number}
      </div>
    `;

    item.addEventListener("mouseenter", function () {
      this.style.backgroundColor = "#f8f9fa";
    });

    item.addEventListener("mouseleave", function () {
      this.style.backgroundColor = "transparent";
    });

    item.addEventListener("click", function () {
      selectCustomer(customer, onSelect);
    });

    dropdown.appendChild(item);
  });

  container.appendChild(dropdown);
}

/**
 * Hide customer dropdown
 */
export function hideCustomerDropdown() {
  const existing = document.querySelector(".dropdown-results");
  if (existing) {
    existing.remove();
  }
}

/**
 * Select a customer and populate fields
 */
export function selectCustomer(customer, onSelect = null) {
  const customerIdInput = document.getElementById("customerId");
  const accountInput = document.getElementById("customerAccount");
  const nameInput = document.getElementById("customerName");
  const addressInput = document.getElementById("customerAddress");

  if (customerIdInput) customerIdInput.value = customer.id;
  if (accountInput) accountInput.value = customer.account_number;
  if (nameInput) nameInput.value = customer.name;
  if (addressInput) addressInput.value = customer.address || "";

  hideCustomerDropdown();

  if (onSelect) {
    onSelect(customer);
  }
}

// ==================== PRODUCT SEARCH & DROPDOWN (API-BASED) ====================

/**
 * Setup product search autocomplete on a product code input
 * @param {HTMLElement} inputElement - The input element to attach search to
 */
export function setupProductSearch(inputElement) {
  if (!inputElement) return;

  inputElement.addEventListener("input", function(e) {
    const value = e.target.value;
    clearTimeout(inputElement._searchTimeout);
    
    if (value.length >= 2) {
      inputElement._searchTimeout = setTimeout(() => {
        searchProductsAPI(value, inputElement);
      }, 300);
    } else {
      hideDropdown(inputElement);
    }
  });

  inputElement.addEventListener("blur", function () {
    setTimeout(() => {
      if (!document.querySelector(".dropdown-results:hover")) {
        hideDropdown(inputElement);
      }
    }, 200);
  });
}

/**
 * Search products via API
 */
export async function searchProductsAPI(query, inputElement) {
  try {
    const response = await fetch(
      `/api/products/search?q=${encodeURIComponent(query)}`
    );
    const products = await response.json();

    if (products.length > 0) {
      showProductDropdown(products, inputElement);
    } else {
      hideDropdown(inputElement);
    }
  } catch (error) {
    console.error("Error searching products:", error);
  }
}

/**
 * Display product search dropdown
 */
export function showProductDropdown(products, inputElement) {
  hideDropdown(inputElement);

  const dropdown = document.createElement("div");
  dropdown.className = "dropdown-results";
  dropdown.style.position = "absolute";
  dropdown.style.zIndex = "1000";
  dropdown.style.backgroundColor = "white";
  dropdown.style.border = "1px solid #ddd";
  dropdown.style.borderRadius = "4px";
  dropdown.style.maxWidth = "500px";
  dropdown.style.boxShadow = "0 2px 4px rgba(0,0,0,0.1)";
  dropdown.style.maxHeight = "300px";
  dropdown.style.overflowY = "auto";

  products.forEach((product) => {
    const item = document.createElement("div");
    item.className = "dropdown-item";
    item.style.padding = "8px 12px";
    item.style.cursor = "pointer";
    item.innerHTML = `
      <strong>${product.code}</strong>
      <div style="font-size: 0.85em; color: #666;">${product.name}</div>
    `;

    item.addEventListener("mouseenter", function () {
      this.style.backgroundColor = "#f8f9fa";
    });

    item.addEventListener("mouseleave", function () {
      this.style.backgroundColor = "transparent";
    });

    item.addEventListener("click", function () {
      selectProduct(product, inputElement);
      hideDropdown(inputElement);
    });

    dropdown.appendChild(item);
  });

  inputElement.parentElement.appendChild(dropdown);
}

/**
 * Select a product and populate fields
 */
export function selectProduct(product, inputElement) {
  const productRow = inputElement.closest(".product-row");
  
  if (productRow) {
    const codeInput = productRow.querySelector(".product-code");
    const nameInput = productRow.querySelector(".product-name");

    if (codeInput) codeInput.value = product.code;
    if (nameInput) nameInput.value = product.name;
  }
}

/**
 * Hide dropdown for a specific input
 */
export function hideDropdown(inputElement) {
  const existing = inputElement.parentElement.querySelector(".dropdown-results");
  if (existing) {
    existing.remove();
  }
}

// ==================== LOCALSTORAGE UTILITIES ====================

export function getLocalStorage(key, defaultValue = null) {
  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : defaultValue;
  } catch (error) {
    console.error(`Error reading from localStorage (${key}):`, error);
    return defaultValue;
  }
}

export function setLocalStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (error) {
    console.error(`Error writing to localStorage (${key}):`, error);
    return false;
  }
}

export function removeLocalStorage(key) {
  try {
    localStorage.removeItem(key);
    return true;
  } catch (error) {
    console.error(`Error removing from localStorage (${key}):`, error);
    return false;
  }
}

// ==================== CUSTOMER UTILITIES (LOCALSTORAGE) ====================

export function normalizeCustomer(customer) {
  if (!customer) return null;

  if (Array.isArray(customer.addresses) && customer.addresses.length > 0) {
    return customer;
  }

  const normalized = { ...customer };
  normalized.addresses = [
    {
      label: "Primary",
      street: customer.street || "",
      city: customer.city || "",
      state: customer.state || "",
      zip: customer.zip || "",
      country: customer.country || "",
    },
  ];

  return normalized;
}

export function autofillAddressFields(form, address, prefix = "") {
  if (!form || !address) return;

  const fields = {
    street: `${prefix}Street`,
    city: `${prefix}City`,
    state: `${prefix}State`,
    zip: `${prefix}Zip`,
    country: `${prefix}Country`,
  };

  Object.keys(fields).forEach((key) => {
    const field = form.querySelector(`#${fields[key]}`);
    if (field && address[key]) {
      field.value = address[key];
    }
  });
}

export function getAllCustomers() {
  return getLocalStorage("customerDatabase", []);
}

export function getCustomerByName(name) {
  const customers = getAllCustomers();
  const customer = customers.find((c) => c.name === name);
  return customer ? normalizeCustomer(customer) : null;
}

export function saveCustomer(customer) {
  const data = localStorage.getItem("customerDatabase");
  const customers = data ? JSON.parse(data) : [];

  const existingIndex = customers.findIndex((c) => c.name === customer.name);

  if (existingIndex !== -1) {
    customers[existingIndex] = customer;
  } else {
    customers.push(customer);
  }

  localStorage.setItem("customerDatabase", JSON.stringify(customers));
  return true;
}

// ==================== PRODUCT UTILITIES (LOCALSTORAGE) ====================

export function getAllProducts() {
  return getLocalStorage("productDatabase", []);
}

export function searchProducts(query) {
  if (!query) return [];

  const products = getAllProducts();
  const searchTerm = query.toLowerCase();

  return products.filter(
    (product) =>
      product.name.toLowerCase().includes(searchTerm) ||
      (product.code && product.code.toLowerCase().includes(searchTerm))
  );
}

export function getProductByCode(code) {
  if (!code) return null;
  const products = getAllProducts();
  return products.find((p) => p.code === code) || null;
}

export function getProductByName(name) {
  if (!name) return null;
  const products = getAllProducts();
  return products.find((p) => p.name === name) || null;
}

// ==================== ADDRESS SELECTOR ====================

export async function setupAddressSelector(
  customer,
  container,
  onAddressSelected
) {
  try {
    const response = await fetch(`/api/customer/${customer.id}/addresses`);
    const addresses = await response.json();

    const existingSelector = container.querySelector(
      ".address-selector-container"
    );
    if (existingSelector) {
      existingSelector.remove();
    }

    if (!addresses || addresses.length === 0) {
      if (onAddressSelected) onAddressSelected(null, null);
      return;
    }

    if (addresses.length === 1) {
      if (onAddressSelected)
        onAddressSelected(addresses[0], addresses[0].label);
      return;
    }

    const selectorHtml = `
      <div class="address-selector-container mb-3">
        <label class="form-label">Select Location *</label>
        <select class="form-select address-location-select" required>
          <option value="">Choose delivery location...</option>
          ${addresses
            .map(
              (addr, idx) => `
            <option value="${idx}" data-label="${addr.label}">
              ${addr.label}${addr.phone ? " - " + addr.phone : ""}
            </option>
          `
            )
            .join("")}
        </select>
      </div>
    `;

    container.insertAdjacentHTML("beforeend", selectorHtml);

    const select = container.querySelector(".address-location-select");
    select.addEventListener("change", function () {
      const idx = parseInt(this.value);
      if (!isNaN(idx) && addresses[idx]) {
        if (onAddressSelected) {
          onAddressSelected(addresses[idx], addresses[idx].label);
        }
      }
    });
  } catch (error) {
    console.error("Error setting up address selector:", error);
  }
}

// ==================== FORM VALIDATION ====================

export function validateForm(form, requiredFields) {
  const errors = [];

  requiredFields.forEach((fieldId) => {
    const field = form.querySelector(`#${fieldId}`);
    if (!field) {
      errors.push(`Field ${fieldId} not found`);
      return;
    }

    if (!field.value || field.value.trim() === "") {
      const label = form.querySelector(`label[for="${fieldId}"]`);
      const fieldName = label ? label.textContent : fieldId;
      errors.push(`${fieldName} is required`);
    }
  });

  return {
    isValid: errors.length === 0,
    errors: errors,
  };
}

export function displayValidationErrors(errors, errorContainer = null) {
  if (errorContainer) {
    errorContainer.innerHTML = errors
      .map((err) => `<div class="error">${err}</div>`)
      .join("");
    errorContainer.style.display = "block";
  } else {
    alert("Please fix the following errors:\n\n" + errors.join("\n"));
  }
}

export function clearValidationErrors(errorContainer) {
  if (errorContainer) {
    errorContainer.innerHTML = "";
    errorContainer.style.display = "none";
  }
}