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

// ==================== CUSTOMER UTILITIES ====================

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

// ==================== CUSTOMER SELECTOR ====================

export function initCustomerSelector(formElement, options = {}) {
  const config = {
    customerSelectId: "customer",
    addressSelectId: "customerAddress",
    addressContainerId: "addressContainer",
    onCustomerChange: null,
    onAddressChange: null,
    ...options,
  };

  const customerSelect = formElement.querySelector(
    `#${config.customerSelectId}`
  );
  const addressSelect = formElement.querySelector(`#${config.addressSelectId}`);
  const addressContainer = formElement.querySelector(
    `#${config.addressContainerId}`
  );

  if (!customerSelect) {
    console.error("Customer select element not found");
    return null;
  }

  let customers = [];
  let currentCustomer = null;
  let currentAddress = null;

  function loadCustomers() {
    const data = localStorage.getItem("customerDatabase");
    customers = data ? JSON.parse(data) : [];
    return customers;
  }

  function populateCustomerSelect() {
    customerSelect.innerHTML = '<option value="">Select Customer...</option>';

    customers.forEach((customer, index) => {
      const option = document.createElement("option");
      option.value = index;
      option.textContent = customer.name;
      customerSelect.appendChild(option);
    });
  }

  function populateAddressSelect(customer) {
    if (!addressSelect || !addressContainer) return;

    const normalized = normalizeCustomer(customer);

    if (normalized.addresses.length === 1) {
      addressContainer.style.display = "none";
      currentAddress = normalized.addresses[0];
      return;
    }

    addressContainer.style.display = "block";
    addressSelect.innerHTML = '<option value="">Select Address...</option>';

    normalized.addresses.forEach((address, index) => {
      const option = document.createElement("option");
      option.value = index;
      option.textContent = `${address.label} - ${address.street}, ${address.city}`;
      addressSelect.appendChild(option);
    });

    if (normalized.addresses.length > 0) {
      addressSelect.value = "0";
      currentAddress = normalized.addresses[0];
    }
  }

  function handleCustomerChange() {
    const selectedIndex = customerSelect.value;

    if (selectedIndex === "") {
      currentCustomer = null;
      currentAddress = null;
      if (addressContainer) {
        addressContainer.style.display = "none";
      }
      if (config.onCustomerChange) {
        config.onCustomerChange(null, null);
      }
      return;
    }

    currentCustomer = normalizeCustomer(customers[selectedIndex]);
    populateAddressSelect(currentCustomer);

    if (config.onCustomerChange) {
      config.onCustomerChange(currentCustomer, currentAddress);
    }
  }

  function handleAddressChange() {
    if (!currentCustomer || !addressSelect) return;

    const selectedIndex = addressSelect.value;
    if (selectedIndex === "") {
      currentAddress = null;
    } else {
      currentAddress = currentCustomer.addresses[selectedIndex];
    }

    if (config.onAddressChange) {
      config.onAddressChange(currentCustomer, currentAddress);
    }
  }

  function getSelectedCustomer() {
    return currentCustomer;
  }

  function getSelectedAddress() {
    return currentAddress;
  }

  function getSelectedData() {
    if (!currentCustomer || !currentAddress) {
      return null;
    }

    return {
      customer: currentCustomer,
      address: currentAddress,
    };
  }

  function refresh() {
    loadCustomers();
    populateCustomerSelect();

    currentCustomer = null;
    currentAddress = null;
    customerSelect.value = "";
    if (addressContainer) {
      addressContainer.style.display = "none";
    }
  }

  function selectCustomer(customerName, addressIndex = 0) {
    const index = customers.findIndex((c) => c.name === customerName);
    if (index === -1) return false;

    customerSelect.value = index;
    handleCustomerChange();

    if (
      addressSelect &&
      currentCustomer &&
      currentCustomer.addresses.length > 1
    ) {
      addressSelect.value = addressIndex;
      handleAddressChange();
    }

    return true;
  }

  loadCustomers();
  populateCustomerSelect();

  if (addressContainer) {
    addressContainer.style.display = "none";
  }

  customerSelect.addEventListener("change", handleCustomerChange);
  if (addressSelect) {
    addressSelect.addEventListener("change", handleAddressChange);
  }

  return {
    getSelectedCustomer,
    getSelectedAddress,
    getSelectedData,
    refresh,
    selectCustomer,
  };
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

// ==================== PRODUCT UTILITIES ====================

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

// ==================== CALLSHEET UTILITIES ====================

export function getAllCallsheets() {
  return getLocalStorage("callsheets", {});
}

export function getCallsheetForWeek(weekId) {
  const callsheets = getAllCallsheets();
  return callsheets[weekId] || [];
}

export function getCurrentWeekCallsheet() {
  const weekId = getWeekIdentifier();
  return getCallsheetForWeek(weekId);
}

export function saveCallsheetForWeek(weekId, entries) {
  const callsheets = getAllCallsheets();
  callsheets[weekId] = entries;
  return setLocalStorage("callsheets", callsheets);
}

export function addToCurrentCallsheet(entry) {
  const weekId = getWeekIdentifier();
  const entries = getCallsheetForWeek(weekId);
  entries.push(entry);
  return saveCallsheetForWeek(weekId, entries);
}

export function removeCallsheetEntry(weekId, index) {
  const entries = getCallsheetForWeek(weekId);
  if (index >= 0 && index < entries.length) {
    entries.splice(index, 1);
    return saveCallsheetForWeek(weekId, entries);
  }
  return false;
}

// ==================== FORM VALIDATION UTILITIES ====================

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

// ==================== PDF UTILITIES ====================

export function createPDF() {
  const { jsPDF } = window.jspdf;
  return new jsPDF({
    orientation: "portrait",
    unit: "mm",
    format: "a4",
  });
}

export function addPDFHeader(pdf, title, yPosition = 20) {
  pdf.setFontSize(16);
  pdf.setFont(undefined, "bold");
  pdf.text(title, 105, yPosition, { align: "center" });
}

export function addPDFFooter(pdf) {
  const pageCount = pdf.internal.getNumberOfPages();
  pdf.setFontSize(10);

  for (let i = 1; i <= pageCount; i++) {
    pdf.setPage(i);
    pdf.text(
      `Page ${i} of ${pageCount}`,
      pdf.internal.pageSize.getWidth() / 2,
      pdf.internal.pageSize.getHeight() - 10,
      { align: "center" }
    );
  }
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
