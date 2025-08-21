import { useMemo, useState, useEffect } from "react";

/* ---------- helpers ---------- */
const ALL_COUNTRY_OPTIONS = ["US", "UK", "CAN", "DE", "AUS", "UAE"];
const VENDOR_COUNTRY_OPTIONS = ["US", "UK", "CAN", "DE"];
const SELLER_COUNTRY_OPTIONS = ["US", "UK", "CAN", "AUS", "DE", "UAE"];
const clamp = (n, min, max) => Math.max(min, Math.min(max, n));

// Get country options based on seller type
const getCountryOptions = (sellerType) => {
  if (sellerType === "vendor") {
    return VENDOR_COUNTRY_OPTIONS;
  } else if (sellerType === "existing_seller" || sellerType === "new_seller") {
    return SELLER_COUNTRY_OPTIONS;
  }
  return ALL_COUNTRY_OPTIONS; // Default fallback
};

// URL validation helper
const isValidUrl = (url) => {
  try {
    const urlObj = new URL(url);
    return urlObj.hostname.toLowerCase().includes('amazon.');
  } catch {
    return false;
  }
};

// Validation helper
const validateStep1 = (brands) => {
  const errors = [];
  
  brands.forEach((brand, brandIndex) => {
    if (!brand.name.trim()) {
      errors.push(`Brand ${brandIndex + 1}: Brand name is required`);
    }
    
    if (!brand.sellerType) {
      errors.push(`Brand ${brandIndex + 1}: Seller type is required`);
    }
    
    brand.countries.forEach((country, countryIndex) => {
      if (!country.name) {
        errors.push(`Brand ${brandIndex + 1}, Country ${countryIndex + 1}: Country is required`);
      }
      if (!country.count || country.count < 1) {
        errors.push(`Brand ${brandIndex + 1}, Country ${countryIndex + 1}: Product count must be at least 1`);
      }
    });
  });
  
  return errors;
};

const validateStep2 = (detail) => {
  const errors = [];
  
  detail.forEach((brand, brandIndex) => {
    brand.countries.forEach((country, countryIndex) => {
      country.products.forEach((product, productIndex) => {
        if (!product.productname.trim()) {
          errors.push(`Brand "${brand.brand}", Country "${country.name}", Product ${productIndex + 1}: Product name is required`);
        }
        if (!product.url.trim()) {
          errors.push(`Brand "${brand.brand}", Country "${country.name}", Product ${productIndex + 1}: Product URL is required`);
        } else if (!isValidUrl(product.url)) {
          errors.push(`Brand "${brand.brand}", Country "${country.name}", Product ${productIndex + 1}: Product URL must be a valid Amazon URL`);
        }
        if (!product.keyword.trim()) {
          errors.push(`Brand "${brand.brand}", Country "${country.name}", Product ${productIndex + 1}: Keyword is required`);
        }
        if (!product.categoryUrl.trim()) {
          errors.push(`Brand "${brand.brand}", Country "${country.name}", Product ${productIndex + 1}: Category URL is required`);
        } else if (!isValidUrl(product.categoryUrl)) {
          errors.push(`Brand "${brand.brand}", Country "${country.name}", Product ${productIndex + 1}: Category URL must be a valid Amazon URL`);
        }
        if (!product.csvFile) {
          errors.push(`Brand "${brand.brand}", Country "${country.name}", Product ${productIndex + 1}: CSV file is required`);
        } else if (!product.csvFile.name.toLowerCase().endsWith('.csv')) {
          errors.push(`Brand "${brand.brand}", Country "${country.name}", Product ${productIndex + 1}: File must be a CSV file`);
        }
      });
    });
  });
  
  return errors;
};

/* ---------- app ---------- */
export default function App() {
  const [step, setStep] = useState(1);
  const [showErrors, setShowErrors] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [backendStatus, setBackendStatus] = useState('checking');
  const [backendError, setBackendError] = useState('');

  // Step 1 data model
  const [brands, setBrands] = useState([
    { name: "", sellerType: "", countries: [{ name: "US", count: 1 }] },
  ]);

  // Step 2 data model (built from step 1)
  const [detail, setDetail] = useState([]); // [{brand, countries:[{name, products:[{url, keyword, csvFile}]}]}]
  const sections = useMemo(
    () =>
      detail.flatMap((b, bi) =>
        b.countries.map((c, ci) => ({
          bi,
          ci,
          label: `${b.brand || "Brand"} • ${c.name}`,
        }))
      ),
    [detail]
  );
  const [sectionIndex, setSectionIndex] = useState(0);
  const totalSections = sections.length || 1;
  const progressPct = Math.round((sectionIndex / totalSections) * 100);

  // Check backend status on component mount
  useEffect(() => {
    checkBackendStatus();
    // Check every 30 seconds
    const interval = setInterval(checkBackendStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const checkBackendStatus = async () => {
    try {
      if (window.electronAPI) {
        const result = await window.electronAPI.checkBackendStatus();
        setBackendStatus(result.status);
        setBackendError(result.error || '');
      } else {
        // Fallback for web version
        const response = await fetch('http://localhost:4000/health');
        if (response.ok) {
          setBackendStatus('connected');
          setBackendError('');
        } else {
          setBackendStatus('disconnected');
          setBackendError('Backend responded with error');
        }
      }
    } catch (error) {
      setBackendStatus('disconnected');
      setBackendError(error.message);
    }
  };

  // Enhanced alert function that uses Electron dialogs when available
  const showAlert = async (title, message, type = 'info') => {
    if (window.electronAPI) {
      switch (type) {
        case 'error':
          await window.electronAPI.showErrorDialog(title, message);
          break;
        case 'success':
          await window.electronAPI.showInfoDialog(title, message);
          break;
        default:
          await window.electronAPI.showInfoDialog(title, message);
      }
    } else {
      // Fallback to browser alert
      alert(`${title}\n\n${message}`);
    }
  };

  /* --------- STEP 1 actions --------- */
  const addBrand = () =>
    setBrands((prev) => [
      ...prev,
      { name: "", sellerType: "", countries: [{ name: "US", count: 1 }] },
    ]);

  const removeBrand = (bi) =>
    setBrands((prev) =>
      prev.length === 1 ? prev : prev.filter((_, i) => i !== bi)
    );

  const updateBrandName = (bi, v) =>
    setBrands((prev) => {
      const next = [...prev];
      next[bi].name = v;
      return next;
    });

  const updateSellerType = (bi, v) =>
    setBrands((prev) => {
      const next = [...prev];
      next[bi].sellerType = v;
      
      // Reset countries that are no longer valid for the new seller type
      const validCountries = getCountryOptions(v);
      next[bi].countries = next[bi].countries.map(country => {
        if (!validCountries.includes(country.name)) {
          return { name: validCountries[0], count: country.count };
        }
        return country;
      });
      
      return next;
    });

  const addCountry = (bi) =>
    setBrands((prev) => {
      const next = prev.map((b) => ({
        ...b,
        countries: b.countries.map((c) => ({ ...c })),
      }));
      const validCountries = getCountryOptions(next[bi].sellerType);
      next[bi].countries.push({ name: validCountries[0], count: 1 });
      return next;
    });

  const removeCountry = (bi, ci) =>
    setBrands((prev) => {
      const next = prev.map((b) => ({
        ...b,
        countries: b.countries.map((c) => ({ ...c })),
      }));
      if (next[bi].countries.length > 1) next[bi].countries.splice(ci, 1);
      return next;
    });

  const updateCountryName = (bi, ci, v) =>
    setBrands((prev) => {
      const next = prev.map((b) => ({
        ...b,
        countries: b.countries.map((c) => ({ ...c })),
      }));
      next[bi].countries[ci].name = v;
      return next;
    });

  const updateCount = (bi, ci, v) =>
    setBrands((prev) => {
      const next = prev.map((b) => ({
        ...b,
        countries: b.countries.map((c) => ({ ...c })),
      }));
      next[bi].countries[ci].count = clamp(parseInt(v || "1", 10) || 1, 1, 10);
      return next;
    });

  const goStep2 = async () => {
    // Validate step 1 data
    const step1Errors = validateStep1(brands);
    if (step1Errors.length > 0) {
      const errorMessage = step1Errors.join('\n');
      await showAlert("Validation Errors", errorMessage, 'error');
      return;
    }

    const built = brands.map((b) => ({
      brand: b.name,
      sellerType: b.sellerType,
      countries: b.countries.map((c) => ({
        name: c.name,
        products: Array.from({ length: c.count }, () => ({
          productname: "",
          url: "",
          keyword: "",
          categoryUrl: "",
          csvFile: null, // Initialize csvFile
        })),
      })),
    }));
    setDetail(built);
    setSectionIndex(0);
    setStep(2);
  };

  /* --------- STEP 2 actions --------- */
  const cur = sections[sectionIndex] || { bi: 0, ci: 0 };
  const currentBrand = detail[cur.bi]?.brand || "";
  const currentCountry = detail[cur.bi]?.countries?.[cur.ci];

  const updateProduct = (pi, field, value) =>
    setDetail((prev) => {
      const next = prev.map((b) => ({
        ...b,
        countries: b.countries.map((c) => ({
          ...c,
          products: c.products.map((p) => ({ ...p })),
        })),
      }));
      next[cur.bi].countries[cur.ci].products[pi][field] = value;
      return next;
    });

  const addProduct = () =>
    setDetail((prev) => {
      const next = prev.map((b) => ({
        ...b,
        countries: b.countries.map((c) => ({
          ...c,
          products: c.products.map((p) => ({ ...p })), // deep clone products
        })),
      }));
      const arr = next[cur.bi].countries[cur.ci].products;
      if (arr.length < 10)
        arr.push({ productname: "", url: "", keyword: "", categoryUrl: "", csvFile: null });
      return next;
    });

  const removeProduct = (pi) =>
    setDetail((prev) => {
      const next = prev.map((b) => ({
        ...b,
        countries: b.countries.map((c) => ({
          ...c,
          products: c.products.map((p) => ({ ...p })),
        })),
      }));
      const arr = next[cur.bi].countries[cur.ci].products;
      if (arr.length > 1) arr.splice(pi, 1);
      return next;
    });

  const prevSection = () =>
    setSectionIndex((i) => clamp(i - 1, 0, totalSections - 1));
  const nextSection = () =>
    setSectionIndex((i) => clamp(i + 1, 0, totalSections - 1));

  const handleSubmit = async () => {
    // Check backend connection first
    if (backendStatus !== 'connected') {
      await showAlert(
        "Backend Not Connected", 
        "Please make sure the backend server is running on localhost:4000 before submitting.",
        'error'
      );
      return;
    }

    // Validate step 2 data
    const step2Errors = validateStep2(detail);
    if (step2Errors.length > 0) {
      const errorMessage = step2Errors.join('\n');
      await showAlert("Validation Errors", errorMessage, 'error');
      return;
    }

    // Set loading state
    setIsSubmitting(true);

    // Shape payload to match backend expectations
    const payload = { 
      brands: detail.map(brand => ({
        brand: brand.brand,
        sellerType: brand.sellerType,
        countries: brand.countries.map(country => ({
          name: country.name,
          products: country.products.map(product => ({
            productname: product.productname,
            url: product.url,
            keyword: product.keyword,
            categoryUrl: product.categoryUrl,
            csvFile: product.csvFile ? product.csvFile.name : null // Include csvFile name in payload
          }))
        }))
      }))
    };

    try {
      if (window.electronConsole) {
        window.electronConsole.log("Submitting payload:", payload);
      } else {
        console.log("Submitting payload:", payload);
      }
      
      let result;
      if (window.electronAPI) {
        // Use Electron API for submission with CSV files
        // First, serialize all CSV files for Electron IPC
        const serializedDetail = await Promise.all(
          detail.map(async (brand) => ({
            ...brand,
            countries: await Promise.all(
              brand.countries.map(async (country) => ({
                ...country,
                products: await Promise.all(
                  country.products.map(async (product) => {
                    if (product.csvFile) {
                      // Serialize the file for Electron IPC
                      const fileData = await new Promise((resolve) => {
                        const reader = new FileReader();
                        reader.onload = () => resolve({
                          name: product.csvFile.name,
                          type: product.csvFile.type,
                          data: Array.from(new Uint8Array(reader.result))
                        });
                        reader.readAsArrayBuffer(product.csvFile);
                      });
                      return { ...product, csvFile: fileData };
                    }
                    return product;
                  })
                )
              }))
            )
          }))
        );
        
        const response = await window.electronAPI.submitFormWithFiles(payload, serializedDetail);
        result = response.data;
        
        if (response.success) {
          if (window.electronConsole) {
            window.electronConsole.log("SUBMIT SUCCESS", result);
          } else {
            console.log("SUBMIT SUCCESS", result);
          }
          
          // Show appropriate message based on response
          if (result.message && result.message.includes("queue")) {
            await showAlert("Success", result.message, 'success');
          } else {
            await showAlert("Success", "Submitted successfully! The scraper is now running in the background.", 'success');
          }
          
          // Reset to step 1 after successful submission
          setStep(1);
          setBrands([{ name: "", sellerType: "", countries: [{ name: "US", count: 1 }] }]);
          setDetail([]);
          setSectionIndex(0);
        } else {
          if (window.electronConsole) {
            window.electronConsole.error("SUBMIT ERROR", result);
          } else {
            console.error("SUBMIT ERROR", result);
          }
          await showAlert("Submission Failed", response.error || 'Unknown error', 'error');
        }
      } else {
        // Fallback for web version - use FormData with CSV files
        const formData = new FormData();
        formData.append('brands_data', JSON.stringify(payload));
        
        // Add all CSV files
        detail.forEach(brand => {
          brand.countries.forEach(country => {
            country.products.forEach(product => {
              if (product.csvFile) {
                formData.append('csv_files', product.csvFile);
              }
            });
          });
        });

        const response = await fetch("http://localhost:4000/api/submissions-with-files", {
          method: "POST",
          body: formData,
        });

        result = await response.json();
        
        if (response.ok) {
          if (window.electronConsole) {
            window.electronConsole.log("SUBMIT SUCCESS", result);
          } else {
            console.log("SUBMIT SUCCESS", result);
          }
          
          // Show appropriate message based on response
          if (result.message && result.message.includes("queue")) {
            await showAlert("Success", result.message, 'success');
          } else {
            await showAlert("Success", "Submitted successfully! The scraper is now running in the background.", 'success');
          }
          
          // Reset to step 1 after successful submission
          setStep(1);
          setBrands([{ name: "", sellerType: "", countries: [{ name: "US", count: 1 }] }]);
          setDetail([]);
          setSectionIndex(0);
        } else {
          if (window.electronConsole) {
            window.electronConsole.error("SUBMIT ERROR", result);
          } else {
            console.error("SUBMIT ERROR", result);
          }
          await showAlert("Submission Failed", result.error || 'Unknown error', 'error');
        }
      }
    } catch (e) {
      if (window.electronConsole) {
        window.electronConsole.error("SUBMIT EXCEPTION", e);
      } else {
        console.error("SUBMIT EXCEPTION", e);
      }
      await showAlert("Connection Error", `Failed to submit: ${e.message}`, 'error');
    } finally {
      // Clear loading state
      setIsSubmitting(false);
    }
  };

  /* ---------- UI ---------- */
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      {/* Backend status indicator */}
      <div className={`px-4 py-2 text-sm font-medium ${
        backendStatus === 'connected' 
          ? 'bg-green-900/20 text-green-300 border-b border-green-700/50' 
          : backendStatus === 'checking'
          ? 'bg-yellow-900/20 text-yellow-300 border-b border-yellow-700/50'
          : 'bg-red-900/20 text-red-300 border-b border-red-700/50'
      }`}>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            backendStatus === 'connected' ? 'bg-green-400' 
            : backendStatus === 'checking' ? 'bg-yellow-400' 
            : 'bg-red-400'
          }`}></div>
          {backendStatus === 'connected' && 'Backend Connected'}
          {backendStatus === 'checking' && 'Checking Backend...'}
          {backendStatus === 'disconnected' && `Backend Disconnected${backendError ? `: ${backendError}` : ''}`}
        </div>
      </div>

      {/* progress bar (only step 2 uses it) */}
      {step === 2 && (
        <div className="h-1 w-full bg-slate-800">
          <div
            className="h-1 bg-blue-500 transition-all"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      )}

      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-3xl font-bold">Product Intake</h1>
          <div className="text-sm text-slate-400">
            Step {step} of 2
          </div>
        </div>

        {step === 1 && (
          <div className="space-y-6">
            <div className="bg-blue-900/20 border border-blue-700/50 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <div className="text-blue-400 text-lg">💡</div>
                <div>
                  <h3 className="font-semibold text-blue-300 mb-2">Step 1: Setup Brands & Countries</h3>
                  <p className="text-sm text-slate-300">
                    Add your brands and specify which countries you want to analyze. For each country, 
                    set the number of products you want to process (1-10).
                  </p>
                </div>
              </div>
            </div>
            {brands.map((b, bi) => (
              <div
                key={bi}
                className="bg-slate-800/50 rounded-xl p-6 border border-slate-700"
              >
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
                  <div>
                    <label className="block text-sm mb-1">Brand</label>
                    <input
                      className={`w-full rounded-lg bg-slate-800 border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        b.name && !b.name.trim() 
                          ? 'border-red-500 focus:ring-red-500' 
                          : b.name && b.name.trim()
                          ? 'border-green-500 focus:ring-green-500'
                          : 'border-slate-700'
                      }`}
                      placeholder="e.g. Big Wipes"
                      value={b.name}
                      onChange={(e) => updateBrandName(bi, e.target.value)}
                    />
                    {b.name && !b.name.trim() && (
                      <div className="text-xs text-red-400 mt-1">
                        ⚠️ Brand name cannot be empty
                      </div>
                    )}
                  </div>
                  <div>
                    <label className="block text-sm mb-1">Seller Type</label>
                    <select
                      className={`w-full rounded-lg bg-slate-800 border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        b.sellerType && b.sellerType.trim() 
                          ? 'border-green-500 focus:ring-green-500'
                          : 'border-slate-700'
                      }`}
                      value={b.sellerType}
                      onChange={(e) => updateSellerType(bi, e.target.value)}
                    >
                      <option value="">Select seller type...</option>
                      <option value="existing_seller">Existing Seller</option>
                      <option value="new_seller">New Seller</option>
                      <option value="vendor">Vendor</option>
                    </select>
                                         {!b.sellerType && (
                       <div className="text-xs text-red-400 mt-1">
                         ⚠️ Seller type is required
                       </div>
                     )}
                     {b.sellerType && (
                       <div className="text-xs text-blue-400 mt-1">
                         {b.sellerType === "vendor" 
                           ? "Available countries: US, UK, CAN, DE"
                           : "Available countries: US, UK, CAN, AUS, DE, UAE"
                         }
                       </div>
                     )}
                  </div>
                  {brands.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeBrand(bi)}
                      className="px-3 py-2 rounded-lg bg-red-600 hover:bg-red-700"
                    >
                      Remove brand
                    </button>
                  )}
                </div>

                <div className="mt-5 space-y-4">
                  <div className="text-sm font-medium opacity-80">
                    Countries & product counts
                  </div>
                  {b.countries.map((c, ci) => (
                    <div
                      key={ci}
                      className="grid grid-cols-1 md:grid-cols-3 gap-3 bg-slate-800/60 p-4 rounded-lg border border-slate-700"
                    >
                      <div>
                        <label className="block text-xs mb-1">Country</label>
                        <select
                          className="w-full rounded-lg bg-slate-900 border border-slate-700 px-3 py-2 focus:ring-2 focus:ring-blue-500"
                          value={c.name}
                          onChange={(e) =>
                            updateCountryName(bi, ci, e.target.value)
                          }
                        >
                          {getCountryOptions(b.sellerType).map((opt) => (
                            <option key={opt} value={opt}>
                              {opt}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs mb-1">
                          Number of products (1–10)
                        </label>
                        <input
                          type="number"
                          min={1}
                          max={10}
                          className="w-full rounded-lg bg-slate-900 border border-slate-700 px-3 py-2 focus:ring-2 focus:ring-blue-500"
                          value={c.count}
                          onChange={(e) => updateCount(bi, ci, e.target.value)}
                        />
                      </div>
                      <div className="flex items-end gap-2">
                        <button
                          type="button"
                          onClick={() => removeCountry(bi, ci)}
                          className="px-3 py-2 rounded-lg bg-slate-700 hover:bg-slate-600"
                        >
                          Remove country
                        </button>
                      </div>
                    </div>
                  ))}

                  <button
                    type="button"
                    onClick={() => addCountry(bi)}
                    className="px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-700"
                  >
                    + Add country
                  </button>
                </div>
              </div>
            ))}

            <div className="flex gap-3">
              <button
                type="button"
                onClick={addBrand}
                className="px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-700"
              >
                + Add brand
              </button>

              <button
                type="button"
                onClick={goStep2}
                className="ml-auto px-4 py-2 rounded-lg bg-green-600 hover:bg-green-700"
              >
                Next →
              </button>
            </div>
          </div>
        )}

        {step === 2 && currentCountry && (
          <div className="space-y-6">
            <div className="bg-green-900/20 border border-green-700/50 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <div className="text-green-400 text-lg">📝</div>
                <div>
                  <h3 className="font-semibold text-green-300 mb-2">Step 2: Product Details</h3>
                  <p className="text-sm text-slate-300">
                    Fill in the details for each product. Make sure all URLs are valid Amazon URLs 
                    (must contain "amazon.com"). All fields are required.
                  </p>
                </div>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm opacity-70">Section</div>
                <div className="text-xl font-semibold">
                  {sections[sectionIndex]?.label}
                </div>
              </div>
              <div className="text-sm opacity-70">
                {sectionIndex + 1} / {totalSections}
              </div>
            </div>

            {/* products list for current brand+country */}
            <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700 space-y-3">
              {currentCountry.products.map((p, pi) => (
                <div
                  key={pi}
                  className="grid grid-cols-1 md:grid-cols-15 gap-3 bg-slate-900/60 p-4 rounded-lg border border-slate-700"
                >
                  <div className="md:col-span-4">
                    <label className="block text-xs mb-1">
                      Product name
                    </label>
                    <input
                      className={`w-full rounded-lg bg-slate-900 border px-3 py-2 focus:ring-2 focus:ring-blue-500 ${
                        p.productname && !p.productname.trim() 
                          ? 'border-red-500 focus:ring-red-500' 
                          : p.productname && p.productname.trim()
                          ? 'border-green-500 focus:ring-green-500'
                          : 'border-slate-700'
                      }`}
                      value={p.productname}
                      onChange={(e) => updateProduct(pi, "productname", e.target.value)}
                      placeholder="cricket bat"
                    />
                    {p.productname && !p.productname.trim() && (
                      <div className="text-xs text-red-400 mt-1">
                        ⚠️ Product name cannot be empty
                      </div>
                    )}
                  </div>

                  <div className="md:col-span-4">
                    <label className="block text-xs mb-1">
                      Amazon Product Listing URL
                    </label>
                    <input
                      className={`w-full rounded-lg bg-slate-900 border px-3 py-2 focus:ring-2 focus:ring-blue-500 ${
                        p.url && !isValidUrl(p.url) 
                          ? 'border-red-500 focus:ring-red-500' 
                          : p.url && isValidUrl(p.url)
                          ? 'border-green-500 focus:ring-green-500'
                          : 'border-slate-700'
                      }`}
                      value={p.url}
                      onChange={(e) => updateProduct(pi, "url", e.target.value)}
                      placeholder="https://www.amazon.com/..."
                    />
                    {p.url && !isValidUrl(p.url) && (
                      <div className="text-xs text-red-400 mt-1">
                        ⚠️ Please enter a valid Amazon URL
                      </div>
                    )}
                    {p.url && isValidUrl(p.url) && (
                      <div className="text-xs text-green-400 mt-1">
                        ✅ Valid Amazon URL
                      </div>
                    )}
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-xs mb-1">Keyword</label>
                    <input
                      className={`w-full rounded-lg bg-slate-900 border px-3 py-2 focus:ring-2 focus:ring-blue-500 ${
                        p.keyword && !p.keyword.trim() 
                          ? 'border-red-500 focus:ring-red-500' 
                          : p.keyword && p.keyword.trim()
                          ? 'border-green-500 focus:ring-green-500'
                          : 'border-slate-700'
                      }`}
                      value={p.keyword}
                      onChange={(e) =>
                        updateProduct(pi, "keyword", e.target.value)
                      }
                      placeholder="e.g. hand wipes"
                    />
                    {p.keyword && !p.keyword.trim() && (
                      <div className="text-xs text-red-400 mt-1">
                        ⚠️ Keyword cannot be empty
                      </div>
                    )}
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-xs mb-1">Category URL</label>
                    <input
                      className={`w-full rounded-lg bg-slate-900 border px-3 py-2 focus:ring-2 focus:ring-blue-500 ${
                        p.categoryUrl && !isValidUrl(p.categoryUrl) 
                          ? 'border-red-500 focus:ring-red-500' 
                          : p.categoryUrl && isValidUrl(p.categoryUrl)
                          ? 'border-green-500 focus:ring-green-500'
                          : 'border-slate-700'
                      }`}
                      value={p.categoryUrl}
                      onChange={(e) =>
                        updateProduct(pi, "categoryUrl", e.target.value)
                      }
                      placeholder="https://www.amazon.com/..."
                    />
                    {p.categoryUrl && !isValidUrl(p.categoryUrl) && (
                      <div className="text-xs text-red-400 mt-1">
                        ⚠️ Please enter a valid Amazon URL
                      </div>
                    )}
                    {p.categoryUrl && isValidUrl(p.categoryUrl) && (
                      <div className="text-xs text-green-400 mt-1">
                        ✅ Valid Amazon URL
                      </div>
                    )}
                  </div>

                  <div className="md:col-span-3">
                    <label className="block text-xs mb-1">CSV File</label>
                    <input
                      type="file"
                      accept=".csv"
                      onChange={(e) => updateProduct(pi, "csvFile", e.target.files[0] || null)}
                      className={`w-full rounded-lg bg-slate-900 border px-3 py-2 focus:ring-2 focus:ring-blue-500 ${
                        p.csvFile && !p.csvFile.name.toLowerCase().endsWith('.csv')
                          ? 'border-red-500 focus:ring-red-500' 
                          : p.csvFile && p.csvFile.name.toLowerCase().endsWith('.csv')
                          ? 'border-green-500 focus:ring-green-500'
                          : 'border-slate-700'
                      }`}
                    />
                    {p.csvFile && (
                      <div className="text-xs text-green-400 mt-1">
                        ✅ {p.csvFile.name}
                      </div>
                    )}
                    {p.csvFile && !p.csvFile.name.toLowerCase().endsWith('.csv') && (
                      <div className="text-xs text-red-400 mt-1">
                        ⚠️ Please select a valid CSV file
                      </div>
                    )}
                  </div>

                  <div className="md:col-span-1 flex items-end">
                    <button
                      type="button"
                      onClick={() => removeProduct(pi)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-700 hover:bg-slate-600"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={addProduct}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700"
                >
                  + Add product
                </button>
              </div>
            </div>

            {/* nav + submit */}
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600"
              >
                ← Back to setup
              </button>

              <button
                type="button"
                onClick={prevSection}
                disabled={sectionIndex === 0}
                className={`px-4 py-2 rounded-lg ${
                  sectionIndex === 0
                    ? "bg-slate-700 opacity-50 cursor-not-allowed"
                    : "bg-slate-700 hover:bg-slate-600"
                }`}
              >
                ← Prev
              </button>

              {sectionIndex < totalSections - 1 ? (
                <button
                  type="button"
                  onClick={nextSection}
                  className="ml-auto px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700"
                >
                  Next →
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={isSubmitting || backendStatus !== 'connected'}
                  className={`ml-auto px-4 py-2 rounded-lg ${
                    isSubmitting || backendStatus !== 'connected'
                      ? "bg-green-400 opacity-50 cursor-not-allowed"
                      : "bg-green-600 hover:bg-green-700"
                  }`}
                >
                  {isSubmitting ? "Submitting..." : "Submit all"}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
