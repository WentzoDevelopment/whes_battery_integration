<p align="center">
  <a href="https://github.com/WentzoDevelopment">
    <img src="https://github.com/WentzoDevelopment.png" 
         alt="Wentzo Logo" width="180" style="border-radius:50%">
  </a>
</p>

# WHES Battery (Home Assistant Integration)

Home Assistant integration for WHES / Weiheng Energy Management System (EMS) and Ammeter metrics. Provided by Wentzo.

This integration allows you to monitor various battery and energy parameters directly in Home Assistant, such as:
- State of Charge (SoC) and State of Health (SoH)
- EMS AC/DC power values
- Grid power per phase

## ⚙️ Configuration
Configuration is handled via the Home Assistant UI (Config Flow).  
Simply provide your **API Key**, **API Secret**, **Project ID**, **Device ID**, and **Ammeter ID**.

## 📦 Installation (via HACS)
1. In Home Assistant, open **HACS → Integrations → ⋯ → Custom repositories**  
   and add this repository (Category: *Integration*).
2. Install **WHES Battery**.
3. Go to **Settings → Devices & Services → Add Integration → “WHES”** and follow the setup flow.

## 🔑 How to Obtain an API Key and Secret
To use this integration, you will need valid API credentials for the WHES platform.

You can request an **API Key** and **API Secret** directly from WHES.  
For more information, visit their [Open API page](https://www.whes.com/platform/open-api) or contact WHES support by email or phone.

## 📘 Developer Documentation
If you would like to extend this integration — for example, by adding new sensors or connecting additional API endpoints — please refer to the official WHES OpenAPI documentation:

[WHES OpenAPI Reference (Pangu v1)](https://www.whes.com/openapi-docs/en/API%20Doc/Pangu/v1/Project.html)

This documentation describes all available endpoints, parameters, and data structures supported by the WHES Pangu platform.
## 🧾 License
This project is licensed under the [MIT License](./LICENSE.md).

## ⚠️ Disclaimer
This integration is provided *as is* without any warranties or official support from Wentzo.  
Use at your own risk.

For questions, suggestions, or bug reports, please use the [Issues](https://github.com/WentzoDevelopment/whes_battery_integration/issues) section on GitHub.

---

*© 2025 Wentzo. WHES and Weiheng are trademarks of their respective owners.*
