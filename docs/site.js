(function () {
  const SEARCH_ITEMS = [
    { label: "Docs Home", href: "./index.html", keywords: "home landing overview" },
    { label: "API Reference", href: "./api-docs.html", keywords: "reference formulas modules" },
    { label: "Tutorials", href: "./tutorials.html", keywords: "training guides notebooks" },
    { label: "Use Cases", href: "./use-cases.html", keywords: "pipeline signs hazop" },
    { label: "Try Now", href: "./app.html", keywords: "app interactive browser local pipeline" },
    { label: "README", href: "./readme.html", keywords: "install deploy package" },
    { label: "Pipeline Workflow", href: "./use-cases.html#pipeline", keywords: "pipeline consequence analysis route source release" },
    { label: "Quick Start", href: "./tutorials.html#quickstart", keywords: "quick start scenario analysis" },
    { label: "Sign Workflow", href: "./use-cases.html#signs", keywords: "sign source release workflow" },
  ];

  function createCommandPalette() {
    const shell = document.createElement("div");
    shell.className = "command-palette-shell";
    shell.innerHTML = `
      <div class="command-palette-backdrop" data-command-close></div>
      <div class="command-palette" role="dialog" aria-modal="true" aria-label="Search Deep Safety">
        <div class="command-palette-head">
          <input class="command-input" type="text" placeholder="Search Deep Safety, tutorials, workflows..." />
          <button class="command-close" type="button" data-command-close aria-label="Close search">Esc</button>
        </div>
        <div class="command-results" data-command-results></div>
      </div>
    `;
    document.body.appendChild(shell);

    const input = shell.querySelector(".command-input");
    const results = shell.querySelector("[data-command-results]");

    function render(query = "") {
      const normalized = query.trim().toLowerCase();
      const items = SEARCH_ITEMS.filter((item) => {
        if (!normalized) {
          return true;
        }
        return `${item.label} ${item.keywords}`.toLowerCase().includes(normalized);
      }).slice(0, 8);

      results.innerHTML = items
        .map(
          (item, index) => `
            <a class="command-result${index === 0 ? " is-active" : ""}" href="${item.href}">
              <span>${item.label}</span>
              <small>${item.keywords}</small>
            </a>
          `,
        )
        .join("");
    }

    function open() {
      shell.classList.add("is-open");
      render("");
      input.value = "";
      window.setTimeout(() => input.focus(), 20);
    }

    function close() {
      shell.classList.remove("is-open");
    }

    input.addEventListener("input", () => render(input.value));
    shell.querySelectorAll("[data-command-close]").forEach((element) => {
      element.addEventListener("click", close);
    });

    document.querySelectorAll("[data-command-trigger]").forEach((trigger) => {
      trigger.addEventListener("click", open);
    });

    document.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        open();
      }
      if (event.key === "Escape") {
        close();
      }
      if (shell.classList.contains("is-open") && event.key === "Enter") {
        const active = shell.querySelector(".command-result");
        if (active && document.activeElement === input) {
          active.click();
        }
      }
    });
  }

  function animateTerminal() {
    const target = document.querySelector("[data-terminal-demo]");
    if (!target) {
      return;
    }

    const scenes = [
      [
        "$ deepsafety try-now",
        "> draw pipeline route",
        "> snap source release at valve station",
        "> run consequence rings",
        "{ status: \"ready\", route: \"west-corridor\", rings: 3 }",
      ],
      [
        "$ deepsafety analyze --mode pipeline",
        "> import GPS corridor",
        "> run receptor screening",
        "> export JSON response",
        "{ receptors: 4, max_radius_m: 182.4, source: \"snapped\" }",
      ],
    ];

    let sceneIndex = 0;
    let charIndex = 0;
    let current = scenes[0].join("\n");

    function step() {
      target.textContent = current.slice(0, charIndex);
      charIndex += 2;
      if (charIndex <= current.length) {
        return;
      }
      window.setTimeout(() => {
        sceneIndex = (sceneIndex + 1) % scenes.length;
        current = scenes[sceneIndex].join("\n");
        charIndex = 0;
      }, 1500);
    }

    step();
    window.setInterval(step, 42);
  }

  function setupPlayground() {
    const root = document.querySelector("[data-playground]");
    if (!root || !window.DeepSafetyBrowserApi) {
      return;
    }

    const examples = {
      pipeline: {
        label: "Pipeline route",
        payload: {
          route: {
            name: "West corridor",
            points: [
              { latitude: 29.759, longitude: -95.364, label: "Segment A" },
              { latitude: 29.761, longitude: -95.359, label: "Segment B" },
              { latitude: 29.764, longitude: -95.354, label: "Segment C" },
            ],
          },
          source: { latitude: 29.7622, longitude: -95.358, label: "Valve station" },
          asset: {
            line_pressure_kpa: 6000,
            gas_temperature_c: 18,
            hole_diameter_m: 0.015,
            leak_duration_s: 90,
            mass_flow_kg_s: 1.25,
            stability_class: "D",
          },
          criteria: [{ label: "Primary ring", threshold: 0.02, unit: "kg/m^3" }],
        },
        run: async (payload) => {
          const route = await window.DeepSafetyBrowserApi.request("POST", "/gis/pipeline-routes", payload.route);
          return window.DeepSafetyBrowserApi.request(
            "POST",
            `/gis/pipeline-routes/${route.id}/impact-zones`,
            {
              scenario_type: "leak",
              source: payload.source,
              asset: payload.asset,
              criteria: payload.criteria,
            },
          );
        },
      },
      source: {
        label: "Source release",
        payload: {
          scenario_type: "leak",
          source: { latitude: 29.7605, longitude: -95.3625, label: "Observed release" },
          receptors: [
            { id: "gate", latitude: 29.7614, longitude: -95.3608, label: "Gate" },
            { id: "control", latitude: 29.7621, longitude: -95.3591, label: "Control room" },
          ],
          inputs: { Q: 25, u: 3.5, stability_class: "D" },
        },
        run: async (payload) =>
          window.DeepSafetyBrowserApi.request("POST", "/gis/scenarios/evaluate", payload),
      },
      rings: {
        label: "Consequence rings",
        payload: {
          scenario_type: "fire",
          source: { latitude: 29.7608, longitude: -95.3631, label: "Pump area" },
          asset: { burning_rate_kg_s: 4.5, heat_of_combustion_kj_kg: 46000 },
          criteria: [
            { label: "Severe ring", threshold: 12.5, unit: "kW/m^2" },
            { label: "Awareness ring", threshold: 4.0, unit: "kW/m^2" },
          ],
        },
        run: async (payload) =>
          window.DeepSafetyBrowserApi.request("POST", "/gis/impact-zones", payload),
      },
    };

    const input = root.querySelector("[data-playground-input]");
    const output = root.querySelector("[data-playground-output]");
    const runButton = root.querySelector("[data-playground-run]");
    const tabs = root.querySelectorAll("[data-playground-example]");
    let active = "pipeline";

    function selectExample(name) {
      active = name;
      input.value = JSON.stringify(examples[name].payload, null, 2);
      tabs.forEach((tab) => {
        tab.classList.toggle("is-active", tab.dataset.playgroundExample === name);
      });
    }

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => selectExample(tab.dataset.playgroundExample));
    });

    runButton.addEventListener("click", async () => {
      runButton.disabled = true;
      runButton.textContent = "Running...";
      output.textContent = "Resolving browser-local workflow...";
      try {
        const payload = JSON.parse(input.value);
        const result = await examples[active].run(payload);
        output.textContent = JSON.stringify(result, null, 2);
      } catch (error) {
        output.textContent = `Error: ${error.message}`;
      } finally {
        runButton.disabled = false;
        runButton.textContent = "Run browser-local";
      }
    });

    selectExample(active);
    output.textContent = JSON.stringify(
      {
        hint: "Select a pipeline, source release, or ring example and run it to see a live JSON response.",
      },
      null,
      2,
    );
  }

  document.addEventListener("DOMContentLoaded", () => {
    createCommandPalette();
    animateTerminal();
    setupPlayground();
  });
})();
