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

// ==================== CUSTOMER SEARCH & ADDRESS SELECTION ====================

let currentSelectedCustomer = null;
let customerSearchTimeout = null;

/**
 * Initialize customer search on a form
 * @param {Object} options - Configuration options
 * @param {string} options.accountInputId - ID of account number input
 * @param {string} options.nameInputId - ID of customer name input
 * @param {string} options.addressInputId - ID of address display input (optional)
 * @param {string} options.addressContainerId - ID of container for address selection (optional)
 * @param {Function} options.onSelect - Callback when customer is selected
 */
export function initCustomerSearch(options = {}) {
  const {
    accountInputId = "customerAccount",
    nameInputId = "customerName",
    addressInputId = "customerAddress",
    addressContainerId = "addressSelectionContainer",
    onSelect = null,
  } = options;

  const accountInput =
    document.getElementById(accountInputId) ||
    document.querySelector(`input[name="${accountInputId}"]`) ||
    document.querySelector('input[name="customer_account"]');
  const nameInput =
    document.getElementById(nameInputId) ||
    document.querySelector(`input[name="${nameInputId}"]`) ||
    document.querySelector('input[name="customer_name"]');

  if (accountInput) {
    setupCustomerInputField(
      accountInput,
      "account",
      addressInputId,
      addressContainerId,
      onSelect
    );
  }

  if (nameInput) {
    setupCustomerInputField(
      nameInput,
      "name",
      addressInputId,
      addressContainerId,
      onSelect
    );
  }

  // Hide dropdowns when clicking outside
  document.addEventListener("click", function (e) {
    if (!e.target.closest(".search-container")) {
      hideAllDropdowns();
    }
  });
}

/**
 * Setup event handlers for a customer search input field
 */
function setupCustomerInputField(
  inputElement,
  searchType,
  addressInputId,
  addressContainerId,
  onSelect
) {
  inputElement.addEventListener("input", function (e) {
    const value = e.target.value.trim();
    clearTimeout(customerSearchTimeout);

    if (value.length < 2) {
      hideCustomerDropdown(inputElement);
      if (searchType === "account") {
        clearCustomerFields(["name", "address"]);
      } else {
        clearCustomerFields(["account", "address"]);
      }
      currentSelectedCustomer = null;
      return;
    }

    customerSearchTimeout = setTimeout(() => {
      searchCustomers(
        value,
        inputElement,
        searchType,
        addressInputId,
        addressContainerId,
        onSelect
      );
    }, 300);
  });

  inputElement.addEventListener("blur", function () {
    setTimeout(() => {
      if (!document.querySelector(".dropdown-results:hover")) {
        hideCustomerDropdown(inputElement);
      }
    }, 200);
  });
}

/**
 * Search for customers via API
 */
async function searchCustomers(
  query,
  inputElement,
  searchType,
  addressInputId,
  addressContainerId,
  onSelect
) {
  try {
    const response = await fetch(
      `/api/customers/search?q=${encodeURIComponent(query)}`
    );

    if (!response.ok) {
      throw new Error("Search failed");
    }

    const customers = await response.json();

    if (customers.length === 0) {
      hideCustomerDropdown(inputElement);
      return;
    }

    showCustomerDropdown(
      customers,
      inputElement,
      searchType,
      addressInputId,
      addressContainerId,
      onSelect
    );
  } catch (error) {
    console.error("Error searching customers:", error);
    hideCustomerDropdown(inputElement);
  }
}

/**
 * Display customer search results dropdown
 */
function showCustomerDropdown(
  customers,
  inputElement,
  searchType,
  addressInputId,
  addressContainerId,
  onSelect
) {
  hideCustomerDropdown(inputElement);

  const dropdown = document.createElement("div");
  dropdown.className = "dropdown-results";
  dropdown.style.cssText = `
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: var(--dark-card, white);
    border: 2px solid var(--border-color, #ddd);
    border-radius: 12px;
    max-height: 250px;
    overflow-y: auto;
    z-index: 1000;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    margin-top: 4px;
  `;

  customers.forEach((customer) => {
    const item = document.createElement("div");
    item.className = "dropdown-item";
    item.style.cssText = `
      padding: 12px 16px;
      cursor: pointer;
      border-bottom: 1px solid var(--border-color, #eee);
      transition: background-color 0.2s;
    `;

    if (searchType === "account") {
      item.innerHTML = `
        <strong>${customer.account_number}</strong>
        <small class="text-muted d-block">${customer.name}</small>
      `;
    } else {
      item.innerHTML = `
        <strong>${customer.name}</strong>
        <small class="text-muted d-block">${customer.account_number}</small>
      `;
    }

    item.addEventListener("mouseenter", function () {
      this.style.backgroundColor = "var(--primary-blue, #007bff)";
      this.style.color = "white";
      const small = this.querySelector("small");
      if (small) small.style.color = "rgba(255, 255, 255, 0.8)";
    });

    item.addEventListener("mouseleave", function () {
      this.style.backgroundColor = "transparent";
      this.style.color = "";
      const small = this.querySelector("small");
      if (small) small.style.color = "";
    });

    item.addEventListener("mousedown", function (e) {
      e.preventDefault();
      selectCustomer(customer, addressInputId, addressContainerId, onSelect);
      hideCustomerDropdown(inputElement);
    });

    dropdown.appendChild(item);
  });

  inputElement.parentElement.appendChild(dropdown);
}

/**
 * Handle customer selection
 */
function selectCustomer(
  customer,
  addressInputId,
  addressContainerId,
  onSelect
) {
  currentSelectedCustomer = customer;

  // Fill in basic customer fields
  const accountInput =
    document.querySelector('input[name="customer_account"]') ||
    document.getElementById("customerAccount");
  const nameInput =
    document.querySelector('input[name="customer_name"]') ||
    document.getElementById("customerName");

  if (accountInput) accountInput.value = customer.account_number;
  if (nameInput) nameInput.value = customer.name;

  // Handle addresses
  handleCustomerAddresses(customer, addressInputId, addressContainerId);

  // Call custom callback if provided
  if (onSelect && typeof onSelect === "function") {
    onSelect(customer);
  }
}

/**
 * Handle address selection based on customer's addresses
 * ALWAYS shows selector with "Add New Address" option
 */
function handleCustomerAddresses(customer, addressInputId, addressContainerId) {
  const addressInput =
    document.querySelector(`input[name="${addressInputId}"]`) ||
    document.getElementById(addressInputId) ||
    document.querySelector('input[name="customer_address"]');

  const addressContainer =
    document.getElementById(addressContainerId) ||
    document.querySelector(".address-selection-area") ||
    document.querySelector(".address-selection-area-modal");

  if (!addressContainer) {
    console.warn("⚠️ No address container found");
    return;
  }

  // Get addresses - check both the addresses array and legacy address field
  let addresses = customer.addresses || [];
  const legacyAddress = customer.address;

  // If no addresses but has legacy address, convert to array format
  if (addresses.length === 0 && legacyAddress) {
    addresses = [
      {
        id: null,
        label: "Primary",
        street: legacyAddress,
        city: "",
        zip: "",
        phone: "",
        is_primary: true,
      },
    ];
  }

  console.log("📍 Customer has", addresses.length, "address(es)");

  // ALWAYS show the selector - even for 0 or 1 addresses
  showAddressSelector(addresses, addressContainer, addressInput, customer.name);
}

/**
 * Show address selector when customer has multiple addresses
 */
function showAddressSelector(addresses, container, addressInput) {
  console.log(
    "📍 Showing address selector with",
    addresses.length,
    "addresses"
  );

  container.innerHTML = `
    <div class="address-selector-wrapper mb-3" style="background: var(--dark-card, #f8f9fa); padding: 15px; border-radius: 8px; border: 2px solid var(--border-color, #dee2e6);">
      <label class="form-label" style="font-weight: 600; color: var(--text-light, #333);">
        <i class="bi bi-geo-alt-fill"></i> Select Delivery Location *
      </label>
      <select class="form-select address-location-select" required style="margin-bottom: 10px;">
        <option value="">Choose location...</option>
        ${addresses
          .map(
            (addr, idx) => `
          <option value="${idx}">
            📍 ${addr.label}${addr.street ? " - " + addr.street : ""}${
              addr.city ? ", " + addr.city : ""
            }
          </option>
        `
          )
          .join("")}
        <option value="new" style="font-weight: 600; color: #28a745;">➕ Add New Address</option>
      </select>
      <div class="selected-address-display mt-2" style="display: none;"></div>
      <div class="new-address-form" style="display: none; margin-top: 15px; padding: 15px; background: var(--dark-bg); border-radius: 8px;">
        <h6 style="color: var(--text-light); margin-bottom: 15px;">
          <i class="bi bi-plus-circle"></i> Add New Delivery Location
        </h6>
        <div class="row g-2">
          <div class="col-md-6">
            <label class="form-label">Location Name *</label>
            <input type="text" class="form-control new-address-label" placeholder="e.g., Main Office, Warehouse 2">
          </div>
          <div class="col-md-6">
            <label class="form-label">Street Address</label>
            <input type="text" class="form-control new-address-street" placeholder="123 Main St">
          </div>
          <div class="col-md-6">
            <label class="form-label">City</label>
            <input type="text" class="form-control new-address-city" placeholder="Glasgow">
          </div>
          <div class="col-md-6">
            <label class="form-label">Postcode</label>
            <input type="text" class="form-control new-address-zip" placeholder="G1 1AA">
          </div>
          <div class="col-md-6">
            <label class="form-label">Phone Number</label>
            <input type="text" class="form-control new-address-phone" placeholder="01234 567890">
          </div>
          <div class="col-12 mt-3">
            <button type="button" class="btn btn-success save-new-address-btn">
              <i class="bi bi-check-circle"></i> Save New Address
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  const select = container.querySelector(".address-location-select");
  const displayDiv = container.querySelector(".selected-address-display");
  const newAddressForm = container.querySelector(".new-address-form");

  select.addEventListener("change", function () {
    const selectedValue = this.value;
    console.log("📍 Address selection changed to:", selectedValue);

    if (selectedValue === "new") {
      // Show new address form
      console.log("➕ Showing new address form");
      displayDiv.style.display = "none";
      newAddressForm.style.display = "block";

      if (addressInput) {
        addressInput.value = "";
        addressInput.placeholder = "Enter new address details above";
      }

      // Set a flag that this is a new address
      updateAddressLabel("__NEW_ADDRESS__");
    } else if (selectedValue === "") {
      // No selection
      displayDiv.style.display = "none";
      newAddressForm.style.display = "none";
      if (addressInput) {
        addressInput.value = "";
        addressInput.placeholder = "Select a location above";
      }
      updateAddressLabel("");
    } else {
      // Show selected existing address
      const idx = parseInt(selectedValue);
      const selectedAddress = addresses[idx];
      console.log("✅ Selected address:", selectedAddress.label);

      displayDiv.innerHTML = `
        <div class="alert alert-success" style="margin-top: 10px;">
          <i class="bi bi-check-circle-fill"></i> <strong>${
            selectedAddress.label
          }</strong><br>
          <small>${formatAddressDisplay(selectedAddress)}</small>
        </div>
      `;
      displayDiv.style.display = "block";
      newAddressForm.style.display = "none";

      if (addressInput) {
        addressInput.value = formatAddressDisplay(selectedAddress);
      }

      // Store the selected address label for form submission
      updateAddressLabel(selectedAddress.label);
    }
  });

// Handle save new address button
const saveBtn = container.querySelector('.save-new-address-btn');
if (saveBtn) {
  saveBtn.addEventListener('click', function() {
    const label = newAddressForm.querySelector('.new-address-label').value.trim();
    
    if (!label) {
      alert('Please enter a location name');
      return;
    }
    
    // Collect address data
    const newAddress = {
      label: label,
      street: newAddressForm.querySelector('.new-address-street').value.trim(),
      city: newAddressForm.querySelector('.new-address-city').value.trim(),
      zip: newAddressForm.querySelector('.new-address-zip').value.trim(),
      phone: newAddressForm.querySelector('.new-address-phone').value.trim()
    };
    
    // Hide the form and show confirmation
    newAddressForm.style.display = 'none';
    displayDiv.innerHTML = `
      <div class="alert alert-success" style="margin-top: 10px;">
        <i class="bi bi-check-circle-fill"></i> <strong>New Address Ready</strong><br>
        <strong>${newAddress.label}</strong><br>
        <small>${formatAddressDisplay(newAddress)}</small><br>
        <small class="text-muted">This address will be saved to the customer when you submit the form.</small>
      </div>
    `;
    displayDiv.style.display = 'block';
    
    // Keep dropdown on "Add New Address" option
    select.value = 'new';
    
    // Create hidden inputs with __NEW__ flag
    const form = container.closest('form');
    if (form) {
      // Remove old hidden inputs
      form.querySelectorAll('[name^="new_address_"]').forEach(el => el.remove());
      form.querySelectorAll('[name="address_label"]').forEach(el => el.remove());
      
      // Create all hidden inputs
      const inputs = {
        'address_label': '__NEW__',
        'new_address_label': newAddress.label,
        'new_address_street': newAddress.street,
        'new_address_city': newAddress.city,
        'new_address_zip': newAddress.zip,
        'new_address_phone': newAddress.phone
      };
      
      Object.entries(inputs).forEach(([name, value]) => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = name;
        input.value = value;
        form.appendChild(input);
      });
      
      console.log('✅ Hidden inputs created:', inputs);
    }
    
    // Clear the new address form
    newAddressForm.querySelectorAll('input').forEach(input => input.value = '');
  });
}

  // Helper function to update address label input
  function updateAddressLabel(value) {
    let labelInput =
      document.getElementById("address_label") ||
      document.querySelector('input[name="address_label"]');

    if (!labelInput) {
      // Create hidden input if it doesn't exist
      const form = container.closest("form");
      if (form) {
        labelInput = document.createElement("input");
        labelInput.type = "hidden";
        labelInput.name = "address_label";
        labelInput.id = "address_label";
        form.appendChild(labelInput);
      }
    }

    if (labelInput) {
      labelInput.value = value;
      console.log("📝 Updated address_label input to:", value);
    }
  }
}

/**
 * Format address for display
 */
function formatAddressDisplay(address) {
  const parts = [];
  if (address.street) parts.push(address.street);
  if (address.city) parts.push(address.city);
  if (address.zip) parts.push(address.zip);
  return parts.join(", ") || "Address not specified";
}

/**
 * Get selected address data from container
 */
export function getSelectedAddress(container) {
  if (!container) {
    console.warn("⚠️ No address container provided");
    return null;
  }

  const select = container.querySelector(".address-location-select");
  if (!select) {
    console.log("ℹ️ No address selector found");
    return null;
  }

  const selectedValue = select.value;
  console.log("📍 Getting selected address, value:", selectedValue);

  if (selectedValue === "new") {
    // Return new address data from form
    const newAddressData = {
      label: container.querySelector(".new-address-label")?.value.trim() || "",
      street:
        container.querySelector(".new-address-street")?.value.trim() || "",
      city: container.querySelector(".new-address-city")?.value.trim() || "",
      zip: container.querySelector(".new-address-zip")?.value.trim() || "",
      phone: container.querySelector(".new-address-phone")?.value.trim() || "",
      isNew: true,
    };

    console.log("➕ New address data:", newAddressData);

    // Validate new address has at least a label
    if (!newAddressData.label) {
      alert("Please enter a location name for the new address");
      return null;
    }

    return newAddressData;
  } else if (selectedValue && selectedValue !== "") {
    // Return the label of selected existing address
    const labelInput =
      document.getElementById("address_label") ||
      document.querySelector('input[name="address_label"]');
    const label = labelInput ? labelInput.value : "";

    console.log("✅ Existing address selected:", label);

    return {
      label: label,
      isNew: false,
    };
  }

  console.log("❌ No address selected");
  return null;
}

/**
 * Clear specific customer fields
 */
function clearCustomerFields(fieldsToClear) {
  const fieldMap = {
    account: 'input[name="customer_account"]',
    name: 'input[name="customer_name"]',
    address: 'input[name="customer_address"]',
  };

  fieldsToClear.forEach((field) => {
    const input = document.querySelector(fieldMap[field]);
    if (input) input.value = "";
  });
}

/**
 * Hide customer dropdown for specific input
 */
function hideCustomerDropdown(inputElement) {
  const existing =
    inputElement.parentElement.querySelector(".dropdown-results");
  if (existing) {
    existing.remove();
  }
}

/**
 * Hide all dropdowns on page
 */
function hideAllDropdowns() {
  document.querySelectorAll(".dropdown-results").forEach((dropdown) => {
    dropdown.remove();
  });
}

/**
 * Get currently selected customer
 */
export function getSelectedCustomer() {
  return currentSelectedCustomer;
}

// ==================== PRODUCT SEARCH ====================

let productSearchTimeout = null;

/**
 * Initialize product search on input fields with class 'product-code'
 * Can be called multiple times for dynamic product rows
 */
export function initProductSearch(containerElement = document) {
  const productCodeInputs = containerElement.querySelectorAll(".product-code");

  productCodeInputs.forEach((input) => {
    // Remove existing listeners to prevent duplicates
    input.removeEventListener("input", handleProductInput);
    input.removeEventListener("blur", handleProductBlur);

    // Add new listeners
    input.addEventListener("input", handleProductInput);
    input.addEventListener("blur", handleProductBlur);
  });
}

/**
 * Handle product input event
 */
function handleProductInput(e) {
  const inputElement = e.target;
  const value = inputElement.value.trim();

  clearTimeout(productSearchTimeout);

  if (value.length < 2) {
    hideProductDropdown(inputElement);
    return;
  }

  productSearchTimeout = setTimeout(() => {
    searchProducts(value, inputElement);
  }, 300);
}

/**
 * Handle product blur event
 */
function handleProductBlur(e) {
  const inputElement = e.target;
  setTimeout(() => {
    if (!document.querySelector(".dropdown-results:hover")) {
      hideProductDropdown(inputElement);
    }
  }, 200);
}

/**
 * Search for products via API
 */
async function searchProducts(query, inputElement) {
  try {
    const response = await fetch(
      `/api/products/search?q=${encodeURIComponent(query)}`
    );

    if (!response.ok) {
      throw new Error("Product search failed");
    }

    const products = await response.json();

    if (products.length === 0) {
      hideProductDropdown(inputElement);
      return;
    }

    showProductDropdown(products, inputElement);
  } catch (error) {
    console.error("Error searching products:", error);
    hideProductDropdown(inputElement);
  }
}

/**
 * Display product search results dropdown
 */
function showProductDropdown(products, inputElement) {
  hideProductDropdown(inputElement);

  const dropdown = document.createElement("div");
  dropdown.className = "dropdown-results";
  dropdown.style.cssText = `
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: var(--dark-card, white);
    border: 2px solid var(--border-color, #ddd);
    border-radius: 12px;
    max-height: 250px;
    overflow-y: auto;
    z-index: 1000;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    margin-top: 4px;
  `;

  products.forEach((product) => {
    const item = document.createElement("div");
    item.className = "dropdown-item";
    item.style.cssText = `
      padding: 12px 16px;
      cursor: pointer;
      border-bottom: 1px solid var(--border-color, #eee);
      transition: background-color 0.2s;
    `;

    item.innerHTML = `
      <strong>${product.code}</strong>
      <small class="text-muted d-block">${product.name}</small>
    `;

    item.addEventListener("mouseenter", function () {
      this.style.backgroundColor = "var(--primary-blue, #007bff)";
      this.style.color = "white";
      const small = this.querySelector("small");
      if (small) small.style.color = "rgba(255, 255, 255, 0.8)";
    });

    item.addEventListener("mouseleave", function () {
      this.style.backgroundColor = "transparent";
      this.style.color = "";
      const small = this.querySelector("small");
      if (small) small.style.color = "";
    });

    item.addEventListener("mousedown", function (e) {
      e.preventDefault();
      selectProduct(product, inputElement);
      hideProductDropdown(inputElement);
    });

    dropdown.appendChild(item);
  });

  // Position dropdown relative to the input's container
  const container =
    inputElement.closest(".search-container") || inputElement.parentElement;
  container.style.position = "relative";
  container.appendChild(dropdown);
}

/**
 * Select a product and populate fields
 */
function selectProduct(product, inputElement) {
  const productRow =
    inputElement.closest(".product-row") || inputElement.closest(".row");

  if (productRow) {
    const codeInput = productRow.querySelector(".product-code");
    const nameInput = productRow.querySelector(".product-name");

    if (codeInput) codeInput.value = product.code;
    if (nameInput) nameInput.value = product.name;
  }
}

/**
 * Hide product dropdown for specific input
 */
function hideProductDropdown(inputElement) {
  const container =
    inputElement.closest(".search-container") || inputElement.parentElement;
  const existing = container.querySelector(".dropdown-results");
  if (existing) {
    existing.remove();
  }
}

// ==================== BACKWARD COMPATIBILITY ====================

// Keep old function names for backward compatibility
export function setupCustomerSearch(accountInputId, nameInputId, onSelect) {
  return initCustomerSearch({
    accountInputId,
    nameInputId,
    onSelect,
  });
}

export function setupProductSearch(inputElement) {
  if (inputElement) {
    inputElement.addEventListener("input", handleProductInput);
    inputElement.addEventListener("blur", handleProductBlur);
  }
}

export function setupAddressSelector(container, addresses, onAddressSelected) {
  showAddressSelector(addresses, container, null);
}

export function selectProductFromDropdown(product, inputElement) {
  selectProduct(product, inputElement);
}

export function hideDropdown(inputElement) {
  hideCustomerDropdown(inputElement);
}

// ==================== LOCALSTORAGE UTILITIES ====================

export function getLocalStorage(key, defaultValue = null) {
  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : defaultValue;
  } catch (error) {
    console.error("Error reading from localStorage:", error);
    return defaultValue;
  }
}

export function setLocalStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (error) {
    console.error("Error writing to localStorage:", error);
    return false;
  }
}

export function removeLocalStorage(key) {
  try {
    localStorage.removeItem(key);
    return true;
  } catch (error) {
    console.error("Error removing from localStorage:", error);
    return false;
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
