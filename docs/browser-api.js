(function () {
  const PI = Math.PI;

  const DEFAULT_CONSTANTS = {
    "shared.pi": {
      value: PI,
      unit: "dimensionless",
      description: "Pi used in dispersion and radiation equations.",
      source: "default",
    },
    "shared.absolute_zero_offset_c": {
      value: 273.15,
      unit: "degC",
      description: "Celsius-to-Kelvin offset.",
      source: "default",
    },
    "shared.reference_temperature_c": {
      value: 20.0,
      unit: "degC",
      description: "Reference temperature for flammability limits.",
      source: "default",
    },
    "fire.default_radiative_fraction": {
      value: 0.35,
      unit: "fraction",
      description: "Default fire radiative fraction.",
      source: "default",
    },
    "fire.default_atmospheric_transmissivity": {
      value: 1.0,
      unit: "fraction",
      description: "Default atmospheric transmissivity.",
      source: "default",
    },
  };

  function constantMeta(name) {
    return { name, ...DEFAULT_CONSTANTS[name] };
  }

  function serviceMeta(service_name, model_type, equations, assumptions, constants, references) {
    return { service_name, model_type, equations, assumptions, constants, references };
  }

  function error(message, status = 400) {
    const issue = new Error(message);
    issue.status = status;
    return issue;
  }

  function parseNumber(value, key) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      throw error(`Input '${key}' must be numeric.`);
    }
    return numeric;
  }

  function positive(value, key) {
    const numeric = parseNumber(value, key);
    if (numeric <= 0) {
      throw error(`Input '${key}' must be greater than zero.`);
    }
    return numeric;
  }

  function round(value, decimals = 6) {
    return Number(Number(value).toFixed(decimals));
  }

  function erf(x) {
    const sign = x >= 0 ? 1 : -1;
    const a1 = 0.254829592;
    const a2 = -0.284496736;
    const a3 = 1.421413741;
    const a4 = -1.453152027;
    const a5 = 1.061405429;
    const p = 0.3275911;
    const abs = Math.abs(x);
    const t = 1 / (1 + p * abs);
    const y = 1 - (((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * Math.exp(-abs * abs));
    return sign * y;
  }

  function probitProbability(probitValue) {
    const z = probitValue - 5;
    return 0.5 * (1 + erf(z / Math.sqrt(2)));
  }

  function summary(model) {
    return {
      id: model.id,
      name: model.name,
      domain: model.domain,
      summary: model.summary,
      consequence_areas: model.consequence_areas,
      status: model.status,
      supported_scenarios: model.supported_scenarios,
      gis_ready: model.gis_ready,
    };
  }

  function getConstantValue(constants, name) {
    const match = constants.find((item) => item.name === name);
    return match ? Number(match.value) : Number(DEFAULT_CONSTANTS[name].value);
  }

  function resolveConstants(modelId, overrides = {}) {
    const resolved = {};
    Object.entries(DEFAULT_CONSTANTS).forEach(([name, definition]) => {
      resolved[name] = { name, ...definition };
    });
    Object.entries(overrides).forEach(([name, value]) => {
      if (resolved[name]) {
        resolved[name] = { ...resolved[name], value: Number(value), source: "override" };
      }
    });
    return Object.values(resolved);
  }

  const MODEL_DETAILS = {
    "dispersion.gaussian_puff_ground": {
      id: "dispersion.gaussian_puff_ground",
      name: "Gaussian Puff Ground",
      domain: "dispersion",
      summary: "Instantaneous ground-level Gaussian puff screening concentration.",
      consequence_areas: ["toxic"],
      status: "implemented",
      supported_scenarios: ["leak"],
      gis_ready: true,
      equations: [
        "C = Q / (((2 * pi)^(3/2)) * sigma_y * sigma_z) * exp(-0.5 * ((y / sigma_y)^2 + (z / sigma_z)^2))",
      ],
      input_fields: [],
      output_fields: [],
      constants: [constantMeta("shared.pi")],
      references: [{ title: "Gaussian puff screening relation", notes: "Used for browser-local screening." }],
      notes: [],
    },
    "dispersion.gaussian_puff_screening_radius": {
      id: "dispersion.gaussian_puff_screening_radius",
      name: "Gaussian Puff Screening Radius",
      domain: "dispersion",
      summary: "Circular screening radius for a concentration threshold.",
      consequence_areas: ["toxic"],
      status: "implemented",
      supported_scenarios: ["leak"],
      gis_ready: true,
      equations: ["Solve x where C(x) = concentration_threshold using screening sigma correlations."],
      input_fields: [],
      output_fields: [],
      constants: [constantMeta("shared.pi")],
      references: [{ title: "Gaussian puff screening radius" }],
      notes: ["Screening circle, not a full time-varying footprint."],
    },
    "dispersion.pasquill_gifford_sigma_y": {
      id: "dispersion.pasquill_gifford_sigma_y",
      name: "Pasquill-Gifford Sigma",
      domain: "dispersion",
      summary: "Screening sigma correlations from distance and stability class.",
      consequence_areas: ["toxic"],
      status: "implemented",
      supported_scenarios: ["leak"],
      gis_ready: false,
      equations: ["sigma_y = a * x^(1 + b)", "sigma_z = a * x / ((1 + b * x)^n)"],
      input_fields: [],
      output_fields: [],
      constants: [],
      references: [{ title: "Pasquill-Gifford screening coefficients" }],
      notes: [],
    },
    "fire.flammability_limits": {
      id: "fire.flammability_limits",
      name: "Flammability Limits",
      domain: "fire",
      summary: "Temperature-adjusted lower and upper flammability limits.",
      consequence_areas: ["fire", "explosion"],
      status: "implemented",
      supported_scenarios: ["fire"],
      gis_ready: false,
      equations: [
        "LFL_T = LFL_ref * (T_ref + T_abs) / (T + T_abs)",
        "UFL_T = UFL_ref * (T + T_abs) / (T_ref + T_abs)",
      ],
      input_fields: [],
      output_fields: [],
      constants: [constantMeta("shared.absolute_zero_offset_c"), constantMeta("shared.reference_temperature_c")],
      references: [{ title: "Flammability limit temperature adjustment" }],
      notes: [],
    },
    "fire.point_source_heat_flux": {
      id: "fire.point_source_heat_flux",
      name: "Point Source Heat Flux",
      domain: "fire",
      summary: "Point-source radiant heat flux at a receptor.",
      consequence_areas: ["fire"],
      status: "implemented",
      supported_scenarios: ["fire"],
      gis_ready: true,
      equations: ["q = tau_a * chi_r * m_dot * DeltaH_c / (4 * pi * r^2)"],
      input_fields: [],
      output_fields: [],
      constants: [constantMeta("shared.pi"), constantMeta("fire.default_radiative_fraction"), constantMeta("fire.default_atmospheric_transmissivity")],
      references: [{ title: "Point-source fire radiation screening model" }],
      notes: [],
    },
    "fire.point_source_heat_flux_radius": {
      id: "fire.point_source_heat_flux_radius",
      name: "Point Source Heat Flux Radius",
      domain: "fire",
      summary: "Impact circle for a selected heat flux threshold.",
      consequence_areas: ["fire"],
      status: "implemented",
      supported_scenarios: ["fire"],
      gis_ready: true,
      equations: ["r = sqrt((tau_a * chi_r * m_dot * DeltaH_c) / (4 * pi * q_threshold))"],
      input_fields: [],
      output_fields: [],
      constants: [constantMeta("shared.pi"), constantMeta("fire.default_radiative_fraction"), constantMeta("fire.default_atmospheric_transmissivity")],
      references: [{ title: "Point-source thermal threshold radius" }],
      notes: [],
    },
    "source.terms.release_rate": {
      id: "source.terms.release_rate",
      name: "Release Rate Placeholder",
      domain: "source",
      summary: "Planned placeholder for release-rate registry expansion.",
      consequence_areas: ["toxic", "fire", "explosion"],
      status: "planned",
      supported_scenarios: ["leak"],
      gis_ready: false,
      equations: [],
      input_fields: [],
      output_fields: [],
      constants: [],
      references: [],
      notes: [],
    },
    "toxics.probit.exposure_response": {
      id: "toxics.probit.exposure_response",
      name: "Toxic Exposure Placeholder",
      domain: "effects",
      summary: "Planned placeholder for registry-level toxic response models.",
      consequence_areas: ["toxic"],
      status: "planned",
      supported_scenarios: ["leak"],
      gis_ready: false,
      equations: [],
      input_fields: [],
      output_fields: [],
      constants: [],
      references: [],
      notes: [],
    },
    "explosion.tnt_equivalency": {
      id: "explosion.tnt_equivalency",
      name: "Explosion TNT Placeholder",
      domain: "explosion",
      summary: "Planned placeholder for registry-level TNT equivalency.",
      consequence_areas: ["explosion"],
      status: "planned",
      supported_scenarios: ["fire"],
      gis_ready: false,
      equations: [],
      input_fields: [],
      output_fields: [],
      constants: [],
      references: [],
      notes: [],
    },
  };

  const SCENARIOS = {
    leak: {
      default_model_id: "dispersion.gaussian_puff_ground",
      models: [summary(MODEL_DETAILS["dispersion.gaussian_puff_ground"])],
    },
    fire: {
      default_model_id: "fire.point_source_heat_flux",
      models: [summary(MODEL_DETAILS["fire.point_source_heat_flux"])],
    },
  };

  const TEMPLATES = [
    {
      id: "tank_rupture",
      name: "Tank rupture",
      incident_type: "tank_leak",
      summary: "Large liquid release from storage vessel.",
      default_inventory: { mass_kg: 5000, phase: "liquid" },
      default_equipment: { diameter_m: 8.0 },
      default_failure_mode: "shell_failure",
      recommended_services: ["source_models", "pool_formation", "evaporation", "fire_explosion_models"],
    },
    {
      id: "pipeline_leak",
      name: "Pipeline leak",
      incident_type: "pipe_rupture",
      summary: "Pressurized line release for leak and dispersion screening.",
      default_inventory: { mass_kg: 800, phase: "gas" },
      default_equipment: { diameter_m: 0.15 },
      default_failure_mode: "hole",
      recommended_services: ["source_models", "dispersion_models", "effect_models"],
    },
  ];

  const SERVICE_CATALOG = {
    source_models: [
      serviceMeta("source_models", "gas_release", [
        "m_dot = C_d * A * P_0 * sqrt(k / (Z * R * T_0) * (2 / (k + 1))^((k + 1) / (k - 1)))",
        "m_dot = C_d * A * P_0 * sqrt((2*k)/(Z*R*T_0*(k-1)) * (r^(2/k) - r^((k+1)/k)))",
      ], ["Ideal-gas compressible discharge screening relation."], [], [{ title: "Deep Safety source model metadata" }]),
      serviceMeta("source_models", "liquid_release", ["v = C_d * sqrt(2 * g * h)", "v = C_d * sqrt(2 * DeltaP / rho)"], ["Incompressible liquid screening model."], [], [{ title: "Liquid release screening metadata" }]),
      serviceMeta("source_models", "flashing", ["flash_fraction = cp_liquid * (T_storage - T_boil) / latent_heat"], ["Single-step flashing estimate."], [], [{ title: "Flashing screening metadata" }]),
      serviceMeta("source_models", "pool_formation", ["pool_area = mass / (rho * pool_thickness)"], ["Uniform pool thickness screening model."], [], [{ title: "Pool formation screening metadata" }]),
      serviceMeta("source_models", "evaporation", ["m_dot = q'' * A / latent_heat", "m_dot = k_m * A * C_s"], ["Surface-limited evaporation screening model."], [], [{ title: "Evaporation screening metadata" }]),
    ],
    dispersion_models: [
      serviceMeta("dispersion_models", "gaussian_plume", ["C = Q_dot / (2 * pi * u * sigma_y * sigma_z) * exp(-(y^2)/(2*sigma_y^2)) * reflection"], ["Steady-state continuous release screening model."], [], [{ title: "Gaussian plume screening metadata" }]),
      serviceMeta("dispersion_models", "gaussian_puff", ["C = Q / (((2 * pi)^(3/2)) * sigma_y * sigma_z) * exp(-0.5 * ((y / sigma_y)^2 + (z / sigma_z)^2))"], ["Instantaneous puff screening model."], [], [{ title: "Gaussian puff screening metadata" }]),
      serviceMeta("dispersion_models", "dense_gas", ["Reduced-gravity heavy gas slumping proxy."], ["Dense gas screening approximation."], [], [{ title: "Dense gas screening metadata" }]),
    ],
    fire_explosion_models: [
      serviceMeta("fire_explosion_models", "jet_fire", ["q = chi_r * m_dot * DeltaH_c / (4 * pi * r^2)"], ["Point-source radiation screening."], [], [{ title: "Jet fire screening metadata" }]),
      serviceMeta("fire_explosion_models", "pool_fire", ["m_dot = A_pool * m''", "q = chi_r * m_dot * DeltaH_c / (4 * pi * r^2)"], ["Pool fire point-source approximation."], [], [{ title: "Pool fire screening metadata" }]),
      serviceMeta("fire_explosion_models", "fireball_bleve", ["D = 5.8 * M^0.325", "t = 0.45 * M^0.26"], ["Empirical BLEVE screening relations."], [], [{ title: "BLEVE fireball screening metadata" }]),
      serviceMeta("fire_explosion_models", "tnt_equivalency", ["W_TNT = eta * M * DeltaH_c / H_TNT"], ["TNT equivalency screening."], [], [{ title: "TNT equivalency screening metadata" }]),
      serviceMeta("fire_explosion_models", "multi_energy", ["Equivalent TNT scaled by blast strength factor."], ["Multi-energy screening approximation."], [], [{ title: "Multi-energy screening metadata" }]),
      serviceMeta("fire_explosion_models", "vce", ["W_TNT = yield_factor * M_cloud * DeltaH_c / H_TNT"], ["Yield factor driven by cloud size, ignition delay, and congestion."], [], [{ title: "VCE screening metadata" }]),
    ],
    effect_models: [
      serviceMeta("effect_models", "toxic_probit", ["Y = a + b * ln(C^n * t)"], ["Population-based expected fatalities supported."], [], [{ title: "Toxic probit screening metadata" }]),
      serviceMeta("effect_models", "toxic_dose_response", ["Y = a + b * ln(C^n * t)"], ["Dose-response curve generation at fixed exposure duration."], [], [{ title: "Toxic dose-response screening metadata" }]),
      serviceMeta("effect_models", "thermal_probit", ["Y = a + b * ln(I^(4/3) * t)"], ["Population-based expected burn cases supported."], [], [{ title: "Thermal probit screening metadata" }]),
      serviceMeta("effect_models", "thermal_dose_response", ["Y = a + b * ln(I^(4/3) * t)"], ["Burn probability curve generation at fixed exposure duration."], [], [{ title: "Thermal dose-response screening metadata" }]),
      serviceMeta("effect_models", "explosion_probit", ["Y = a + b * ln(P)"], ["Population-based expected fatalities supported."], [], [{ title: "Explosion probit screening metadata" }]),
      serviceMeta("effect_models", "explosion_dose_response", ["Y = a + b * ln(P)"], ["Fatality probability curve generation against overpressure."], [], [{ title: "Explosion dose-response screening metadata" }]),
    ],
    toxic_criteria: [
      serviceMeta("toxic_criteria", "toxic_criteria_lookup", ["Registry lookup and optional caller override merge for toxic criteria values."], ["Starter criteria registry is built in and can be extended through request overrides."], [], [{ title: "Deep Safety toxic criteria registry" }]),
    ],
    prevention_response_models: [
      serviceMeta("prevention_response_models", "fire_triangle_screening", ["Fire possible when fuel, oxidizer, and ignition source are all present."], ["Boolean fire triangle screening check."], [], [{ title: "Fire triangle screening" }]),
      serviceMeta("prevention_response_models", "autoignition_screening", ["safety_margin = T_autoignition - T_process"], ["Temperature margin used as a screening ignition indicator."], [], [{ title: "Autoignition temperature screening" }]),
      serviceMeta("prevention_response_models", "inerting_requirement", ["V_inert = V_protected * (x_O2,initial - x_O2,target) / purity"], ["Well-mixed oxygen dilution screening model."], [], [{ title: "Inerting requirement screening" }]),
      serviceMeta("prevention_response_models", "ignition_energy_screening", ["energy_ratio = E_source / MIE"], ["Compares source energy against minimum ignition energy."], [], [{ title: "Minimum ignition energy screening" }]),
      serviceMeta("prevention_response_models", "spray_mist_screening", ["mist_enhancement_factor = (spray_pressure / droplet_size) * (T_liquid / flash_point)"], ["Atomization and temperature proxies used for spray/mist fire screening."], [], [{ title: "Spray and mist screening approximation" }]),
      serviceMeta("prevention_response_models", "release_prevention_screening", ["prevention_score = barriers * P_shutdown / (1 + t_detect/60 + t_isolate/60) * (30 / inspection_interval_days)"], ["Barrier count, response time, and inspection interval are combined into a screening score."], [], [{ title: "Release prevention screening" }]),
      serviceMeta("prevention_response_models", "emergency_response_planning", ["urgency_score = population_exposed * release_duration / response_team_time"], ["Compares shelter and evacuation times to propose an initial protective action."], [], [{ title: "Emergency response planning screening" }]),
    ],
    visualization_layers: [
      serviceMeta("visualization_layers", "plume_map", [], ["Downwind plume concentration series."], [], []),
      serviceMeta("visualization_layers", "heatmap", [], ["2D concentration screening grid."], [], []),
      serviceMeta("visualization_layers", "risk_contours", [], ["Map-ready circles and polygons."], [], []),
      serviceMeta("visualization_layers", "time_evolution", [], ["Growing radius frames for timeline sliders."], [], []),
    ],
    sign_intelligence: [
      serviceMeta("sign_intelligence", "sign_analysis", ["Keyword and phrase matching against normalized sign text."], ["Browser-local sign classification expects OCR text or a manual sign-text hint."], [], [{ title: "Deep Safety sign intelligence heuristics" }]),
    ],
  };

  function sigmaY(x, stabilityClass) {
    const coeffs = {
      A: [0.22, 0.0001],
      B: [0.16, 0.0001],
      C: [0.11, 0.0001],
      D: [0.08, 0.0001],
      E: [0.06, 0.0001],
      F: [0.04, 0.0001],
    };
    const [a, b] = coeffs[String(stabilityClass || "D").toUpperCase()] || coeffs.D;
    return a * Math.pow(x, 1 + b);
  }

  function sigmaZ(x, stabilityClass) {
    const coeffs = {
      A: [0.2, 0.0, 1.0],
      B: [0.12, 0.0, 1.0],
      C: [0.08, 0.0002, 0.5],
      D: [0.06, 0.0015, 0.5],
      E: [0.03, 0.0003, 1.0],
      F: [0.016, 0.0003, 1.0],
    };
    const [a, b, exponent] = coeffs[String(stabilityClass || "D").toUpperCase()] || coeffs.D;
    return (a * x) / Math.pow(1 + b * x, exponent);
  }

  function puffDispersionGround(inputs) {
    const q = positive(inputs.Q, "Q");
    const sigmaYValue = positive(inputs.sigma_y, "sigma_y");
    const sigmaZValue = positive(inputs.sigma_z, "sigma_z");
    const y = parseNumber(inputs.y ?? 0, "y");
    const z = parseNumber(inputs.z ?? 0, "z");
    const coefficient = q / (Math.pow(2 * PI, 1.5) * sigmaYValue * sigmaZValue);
    const exponent = -0.5 * (Math.pow(y / sigmaYValue, 2) + Math.pow(z / sigmaZValue, 2));
    return coefficient * Math.exp(exponent);
  }

  function flammabilityLimits(inputs, constants) {
    const tempC = positive(inputs.temp_c, "temp_c");
    const lfl = positive(inputs.lfl_20c, "lfl_20c");
    const ufl = positive(inputs.ufl_20c, "ufl_20c");
    const absoluteZero = getConstantValue(constants, "shared.absolute_zero_offset_c");
    const referenceTemp = getConstantValue(constants, "shared.reference_temperature_c");
    return {
      lower_flammability_limit: round((lfl * (referenceTemp + absoluteZero)) / (tempC + absoluteZero)),
      upper_flammability_limit: round((ufl * (tempC + absoluteZero)) / (referenceTemp + absoluteZero)),
    };
  }

  function pointSourceHeatFlux(inputs, constants) {
    const distance = positive(inputs.distance_m, "distance_m");
    const burningRate = positive(inputs.burning_rate_kg_s, "burning_rate_kg_s");
    const heat = positive(inputs.heat_of_combustion_kj_kg, "heat_of_combustion_kj_kg");
    const radiativeFraction = getConstantValue(constants, "fire.default_radiative_fraction");
    const transmissivity = getConstantValue(constants, "fire.default_atmospheric_transmissivity");
    return {
      heat_flux_kw_m2: round(
        (transmissivity * radiativeFraction * burningRate * heat) / (4 * PI * Math.pow(distance, 2)),
      ),
    };
  }

  function pointSourceHeatFluxRadius(inputs, constants) {
    const burningRate = positive(inputs.burning_rate_kg_s, "burning_rate_kg_s");
    const heat = positive(inputs.heat_of_combustion_kj_kg, "heat_of_combustion_kj_kg");
    const threshold = positive(inputs.impact_threshold_kw_m2, "impact_threshold_kw_m2");
    const radiativeFraction = getConstantValue(constants, "fire.default_radiative_fraction");
    const transmissivity = getConstantValue(constants, "fire.default_atmospheric_transmissivity");
    const radius = Math.sqrt((transmissivity * radiativeFraction * burningRate * heat) / (4 * PI * threshold));
    return {
      impact_radius_m: round(radius),
      impact_area_m2: round(PI * radius * radius),
    };
  }

  function specificGasConstant(molecularWeightKgKmol) {
    return 8.314462618 / (molecularWeightKgKmol / 1000);
  }

  function dischargeArea(inputs, areaKey, diameterKey) {
    if (inputs[areaKey] != null) {
      return positive(inputs[areaKey], areaKey);
    }
    if (inputs[diameterKey] != null) {
      const diameter = positive(inputs[diameterKey], diameterKey);
      return (PI * diameter * diameter) / 4;
    }
    if (inputs.diameter_m != null) {
      const diameter = positive(inputs.diameter_m, "diameter_m");
      return (PI * diameter * diameter) / 4;
    }
    throw error("Provide an area or diameter for the discharge geometry.");
  }

  function solveSourceModel(modelType, inputs) {
    const name = String(modelType).toLowerCase();
    if (name === "gas_release") {
      const duration = positive(inputs.duration_s, "duration_s");
      const upstreamPressure = positive(inputs.upstream_pressure_pa, "upstream_pressure_pa");
      const downstreamPressure = positive(inputs.downstream_pressure_pa, "downstream_pressure_pa");
      const temperatureK = positive(inputs.temperature_k, "temperature_k");
      const k = positive(inputs.heat_capacity_ratio, "heat_capacity_ratio");
      const molecularWeight = positive(inputs.molecular_weight_kg_kmol, "molecular_weight_kg_kmol");
      const dischargeCoefficient = Number(inputs.discharge_coefficient ?? 0.62);
      const compressibility = Number(inputs.compressibility ?? 1.0);
      const subtype = String(inputs.source_subtype || inputs.discharge_geometry || "hole").toLowerCase();
      const area =
        subtype === "pipe" || subtype === "pipeline" || subtype === "pipe_rupture"
          ? dischargeArea(inputs, "pipe_area_m2", "pipe_diameter_m")
          : subtype === "relief" || subtype === "relief_discharge"
            ? dischargeArea(inputs, "relief_area_m2", "relief_diameter_m")
            : dischargeArea(inputs, "hole_area_m2", "hole_diameter_m");
      const gasConstant = specificGasConstant(molecularWeight);
      const pressureRatio = downstreamPressure / upstreamPressure;
      const criticalRatio = Math.pow(2 / (k + 1), k / (k - 1));
      const choked = pressureRatio <= criticalRatio;
      let massRate;
      if (choked) {
        massRate =
          dischargeCoefficient *
          area *
          upstreamPressure *
          Math.sqrt((k / (compressibility * gasConstant * temperatureK)) * Math.pow(2 / (k + 1), (k + 1) / (k - 1)));
      } else {
        massRate =
          dischargeCoefficient *
          area *
          upstreamPressure *
          Math.sqrt(
            ((2 * k) / (compressibility * gasConstant * temperatureK * (k - 1))) *
              (Math.pow(pressureRatio, 2 / k) - Math.pow(pressureRatio, (k + 1) / k)),
          );
      }
      if ((subtype === "pipe" || subtype === "pipeline" || subtype === "pipe_rupture") && inputs.pipe_length_m && inputs.pipe_diameter_m) {
        const reynolds = Number(inputs.reynolds_number ?? 100000);
        const roughness = Number(inputs.relative_roughness ?? 0.00015);
        const friction =
          reynolds <= 2000
            ? 64 / reynolds
            : 0.25 / Math.pow(Math.log10(roughness / 3.7 + 5.74 / Math.pow(reynolds, 0.9)), 2);
        massRate *= Math.max(
          0.15,
          1 / Math.sqrt(1 + friction * Number(inputs.pipe_length_m) / Number(inputs.pipe_diameter_m)),
        );
      }
      if (subtype === "relief" || subtype === "relief_discharge") {
        massRate *= Number(inputs.relieving_factor ?? 1);
      }
      if (inputs.conservative_mode) {
        massRate *= 1.15;
      }
      let inventoryMass = Number(inputs.inventory_mass_kg ?? massRate * duration);
      if (inputs.vessel_volume_m3 != null) {
        const initialDensity = upstreamPressure / (compressibility * gasConstant * temperatureK);
        const finalPressure = Number(inputs.final_pressure_pa ?? downstreamPressure);
        const finalDensity = finalPressure / (compressibility * gasConstant * temperatureK);
        inventoryMass = Math.min(
          inventoryMass,
          Math.max(0, (initialDensity - finalDensity) * Number(inputs.vessel_volume_m3)),
        );
      }
      const totalMass = Math.min(inventoryMass, massRate * duration);
      const averageRate = totalMass / duration;
      const gasDensity = upstreamPressure / (compressibility * gasConstant * temperatureK);
      return {
        model_type: "gas_release",
        submodel: choked ? "choked_flow" : "non_choked_compressible_flow",
        source_subtype: subtype,
        release_rate_kg_s: round(massRate),
        average_release_rate_kg_s: round(averageRate),
        volumetric_rate_m3_s: round(averageRate / gasDensity),
        total_mass_kg: round(totalMass),
        phase_state: "gas",
        critical_pressure_ratio: round(criticalRatio),
        gas_density_kg_m3: round(gasDensity),
      };
    }

    if (name === "liquid_release") {
      const density = positive(inputs.density_kg_m3, "density_kg_m3");
      const duration = positive(inputs.duration_s, "duration_s");
      const dischargeCoefficient = Number(inputs.discharge_coefficient ?? 0.62);
      const subtype = String(inputs.source_subtype || "hole_in_tank").toLowerCase();
      let velocity;
      let area;
      let submodel;
      if (["hole_in_tank", "tank_leak", "gravity_driven"].includes(subtype)) {
        area = dischargeArea(inputs, "hole_area_m2", "hole_diameter_m");
        velocity = dischargeCoefficient * Math.sqrt(2 * 9.80665 * positive(inputs.liquid_head_m, "liquid_head_m"));
        submodel = "gravity_driven_tank_hole";
      } else {
        area = dischargeArea(inputs, "pipe_area_m2", "pipe_diameter_m");
        velocity = Math.sqrt((2 * positive(inputs.delta_pressure_pa, "delta_pressure_pa")) / density);
        if (inputs.pipe_length_m && inputs.pipe_diameter_m) {
          const reynolds = Number(inputs.reynolds_number ?? 100000);
          const roughness = Number(inputs.relative_roughness ?? 0.00015);
          const friction =
            reynolds <= 2000
              ? 64 / reynolds
              : 0.25 / Math.pow(Math.log10(roughness / 3.7 + 5.74 / Math.pow(reynolds, 0.9)), 2);
          velocity *= Math.max(
            0.15,
            1 / Math.sqrt(1 + friction * Number(inputs.pipe_length_m) / Number(inputs.pipe_diameter_m)),
          );
        }
        velocity *= dischargeCoefficient;
        submodel = "pipe_flow";
      }
      let massRate = area * velocity * density;
      if (inputs.conservative_mode) {
        massRate *= 1.1;
      }
      const inventoryMass = Number(inputs.inventory_mass_kg ?? massRate * duration);
      const totalMass = Math.min(inventoryMass, massRate * duration);
      return {
        model_type: "liquid_release",
        submodel,
        release_rate_kg_s: round(massRate),
        average_release_rate_kg_s: round(totalMass / duration),
        volumetric_rate_m3_s: round(area * velocity),
        total_mass_kg: round(totalMass),
        phase_state: "liquid",
        exit_velocity_m_s: round(velocity),
      };
    }

    if (name === "flashing") {
      const cp = positive(inputs.cp_liquid_j_kg_k, "cp_liquid_j_kg_k");
      const storage = positive(inputs.storage_temperature_k, "storage_temperature_k");
      const boiling = positive(inputs.boiling_point_k, "boiling_point_k");
      const latent = positive(inputs.latent_heat_j_kg, "latent_heat_j_kg");
      const totalMass = positive(inputs.total_mass_kg, "total_mass_kg");
      const entrainment = Math.max(0, Math.min(1, Number(inputs.entrainment_fraction ?? 0)));
      const flashFraction = Math.max(0, Math.min(1, (cp * (storage - boiling)) / latent));
      const vaporMass = totalMass * flashFraction;
      const entrained = (totalMass - vaporMass) * entrainment;
      return {
        model_type: "flashing",
        flash_fraction: round(flashFraction),
        vapor_mass_kg: round(vaporMass),
        entrained_liquid_mass_kg: round(entrained),
        rainout_mass_kg: round(Math.max(totalMass - vaporMass - entrained, 0)),
        phase_state: "two_phase",
      };
    }

    if (name === "pool_formation") {
      const liquidMass = positive(inputs.liquid_mass_kg, "liquid_mass_kg");
      const density = positive(inputs.density_kg_m3, "density_kg_m3");
      const thickness = positive(inputs.pool_thickness_m, "pool_thickness_m");
      const containment = Number(inputs.containment_area_m2 ?? 0);
      const spreadingFactor = Number(inputs.spreading_factor ?? 1);
      const unconstrained = (liquidMass / density / thickness) * spreadingFactor;
      const area = containment > 0 ? Math.min(unconstrained, containment) : unconstrained;
      return {
        model_type: "pool_formation",
        submodel: containment > 0 ? "diked_pool" : "free_spreading_pool",
        pool_area_m2: round(area),
        pool_diameter_m: round(Math.sqrt((4 * area) / PI)),
        contained_fraction: round(unconstrained > 0 ? area / unconstrained : 0),
      };
    }

    if (name === "evaporation") {
      const area = positive(inputs.area_m2, "area_m2");
      const latent = positive(inputs.latent_heat_j_kg, "latent_heat_j_kg");
      if (inputs.heat_flux_kw_m2 != null) {
        return {
          model_type: "evaporation",
          submodel: "heat_transfer_limited",
          evaporation_rate_kg_s: round((positive(inputs.heat_flux_kw_m2, "heat_flux_kw_m2") * 1000 * area) / latent),
        };
      }
      if (inputs.wall_heat_input_kw != null) {
        return {
          model_type: "evaporation",
          submodel: "boiling_heat_input_limited",
          evaporation_rate_kg_s: round((positive(inputs.wall_heat_input_kw, "wall_heat_input_kw") * 1000) / latent),
        };
      }
      return {
        model_type: "evaporation",
        submodel: "mass_transfer_limited",
        evaporation_rate_kg_s: round(
          positive(inputs.mass_transfer_coefficient_m_s, "mass_transfer_coefficient_m_s") *
            area *
            positive(inputs.surface_concentration_kg_m3, "surface_concentration_kg_m3"),
        ),
      };
    }

    throw error("Unsupported source model.");
  }

  function solveDispersionModel(modelType, inputs) {
    const name = String(modelType).toLowerCase();
    if (name === "gaussian_plume") {
      const releaseRate = positive(inputs.release_rate_kg_s, "release_rate_kg_s");
      const wind = positive(inputs.wind_speed_m_s, "wind_speed_m_s");
      const x = positive(inputs.x_m, "x_m");
      const y = Number(inputs.y_m ?? 0);
      const z = Number(inputs.z_m ?? 0);
      const releaseHeight = Number(inputs.release_height_m ?? 0);
      const stability = String(inputs.stability_class ?? "D").toUpperCase();
      const sy = sigmaY(x, stability);
      const sz = sigmaZ(x, stability);
      const reflected =
        Math.exp(-0.5 * Math.pow((z - releaseHeight) / sz, 2)) +
        Math.exp(-0.5 * Math.pow((z + releaseHeight) / sz, 2));
      const concentration =
        (releaseRate / (2 * PI * wind * sy * sz)) * Math.exp(-0.5 * Math.pow(y / sy, 2)) * reflected;
      const threshold = Number(inputs.threshold_kg_m3 ?? 0);
      let thresholdDistance = null;
      if (threshold > 0) {
        for (let distance = 1; distance <= 100000; distance += 50) {
          const trialSy = sigmaY(distance, stability);
          const trialSz = sigmaZ(distance, stability);
          const trialReflection =
            Math.exp(-0.5 * Math.pow(releaseHeight / trialSz, 2)) +
            Math.exp(-0.5 * Math.pow(releaseHeight / trialSz, 2));
          const trialConcentration = (releaseRate / (2 * PI * wind * trialSy * trialSz)) * trialReflection;
          if (trialConcentration <= threshold) {
            thresholdDistance = distance;
            break;
          }
        }
      }
      return {
        model_type: "gaussian_plume",
        concentration_kg_m3: round(concentration, 8),
        sigma_y_m: round(sy),
        sigma_z_m: round(sz),
        plume_width_m: round(2 * sy),
        maximum_concentration_location_m: y === 0 && z === 0 ? x : Math.max(1, x - sy),
        distance_to_threshold_m: thresholdDistance,
      };
    }

    if (name === "gaussian_puff") {
      const releasedMass = positive(inputs.released_mass_kg, "released_mass_kg");
      const x = positive(inputs.x_m, "x_m");
      const stability = String(inputs.stability_class ?? "D").toUpperCase();
      return {
        model_type: "gaussian_puff",
        concentration_kg_m3: round(
          puffDispersionGround({
            Q: releasedMass,
            y: Number(inputs.y_m ?? 0),
            z: Number(inputs.z_m ?? 0),
            sigma_y: sigmaY(x, stability),
            sigma_z: sigmaZ(x, stability),
          }),
          8,
        ),
        sigma_y_m: round(sigmaY(x, stability)),
        sigma_z_m: round(sigmaZ(x, stability)),
        plume_width_m: round(2 * sigmaY(x, stability)),
      };
    }

    if (name === "dense_gas") {
      const releasedMass = positive(inputs.released_mass_kg, "released_mass_kg");
      const gasDensity = positive(inputs.gas_density_kg_m3, "gas_density_kg_m3");
      const airDensity = Number(inputs.air_density_kg_m3 ?? 1.225);
      const duration = positive(inputs.release_duration_s, "release_duration_s");
      const wind = positive(inputs.wind_speed_m_s, "wind_speed_m_s");
      const reducedGravity = Math.max(1e-6, ((gasDensity - airDensity) / airDensity) * 9.81);
      const cloudVolume = releasedMass / gasDensity;
      const radius = Math.pow(cloudVolume / Math.max(0.2, wind), 1 / 3) * Math.sqrt(1 + reducedGravity) * 6;
      const slumpVelocity = Math.sqrt(reducedGravity * Math.max(0.5, radius));
      const length = Math.max(radius, (slumpVelocity * duration) / 3);
      return {
        model_type: "dense_gas",
        cloud_radius_m: round(radius),
        cloud_length_m: round(length),
        gravity_slumping_velocity_m_s: round(slumpVelocity),
        maximum_concentration_location_m: round(length / 2),
      };
    }

    throw error("Unsupported dispersion model.");
  }

  function overpressureFromScaledDistance(z) {
    const clamped = Math.max(z, 0.05);
    return 1772 / Math.pow(clamped, 3) + 114 / Math.pow(clamped, 2) + 10.4 / clamped;
  }

  function solveFireExplosionModel(modelType, inputs) {
    const name = String(modelType).toLowerCase();
    if (name === "jet_fire") {
      const releaseRate = positive(inputs.release_rate_kg_s, "release_rate_kg_s");
      const heat = positive(inputs.heat_of_combustion_kj_kg, "heat_of_combustion_kj_kg");
      const distance = positive(inputs.distance_m, "distance_m");
      const radiativeFraction = Number(inputs.radiative_fraction ?? 0.2);
      return {
        model_type: "jet_fire",
        heat_flux_kw_m2: round((radiativeFraction * releaseRate * heat) / (4 * PI * Math.pow(distance, 2))),
        flame_length_m: round(15 * Math.pow(releaseRate, 0.4)),
      };
    }
    if (name === "pool_fire") {
      const area = positive(inputs.pool_area_m2, "pool_area_m2");
      const flux = positive(inputs.burning_flux_kg_m2_s, "burning_flux_kg_m2_s");
      const heat = positive(inputs.heat_of_combustion_kj_kg, "heat_of_combustion_kj_kg");
      const distance = positive(inputs.distance_m, "distance_m");
      const radiativeFraction = Number(inputs.radiative_fraction ?? 0.35);
      const burningRate = area * flux;
      return {
        model_type: "pool_fire",
        pool_diameter_m: round(Math.sqrt((4 * area) / PI)),
        burning_rate_kg_s: round(burningRate),
        heat_flux_kw_m2: round((radiativeFraction * burningRate * heat) / (4 * PI * Math.pow(distance, 2))),
      };
    }
    if (name === "fireball_bleve") {
      const mass = positive(inputs.fuel_mass_kg, "fuel_mass_kg");
      const heat = positive(inputs.heat_of_combustion_kj_kg, "heat_of_combustion_kj_kg");
      const distance = positive(inputs.distance_m, "distance_m");
      const diameter = 5.8 * Math.pow(mass, 0.325);
      const duration = 0.45 * Math.pow(mass, 0.26);
      const radiativeFraction = Number(inputs.radiative_fraction ?? 0.35);
      return {
        model_type: "fireball_bleve",
        fireball_diameter_m: round(diameter),
        fireball_duration_s: round(duration),
        heat_flux_kw_m2: round((radiativeFraction * mass * heat) / Math.max(1, duration) / (4 * PI * Math.pow(Math.max(distance, 1), 2))),
      };
    }
    if (name === "tnt_equivalency") {
      const mass = positive(inputs.fuel_mass_kg, "fuel_mass_kg");
      const heat = positive(inputs.heat_of_combustion_kj_kg, "heat_of_combustion_kj_kg");
      const efficiency = Number(inputs.explosion_efficiency ?? 0.1);
      const distance = positive(inputs.distance_m, "distance_m");
      const tntMass = (mass * heat * efficiency) / 4680;
      const scaled = distance / Math.pow(Math.max(tntMass, 1e-6), 1 / 3);
      return {
        model_type: "tnt_equivalency",
        tnt_equivalent_mass_kg: round(tntMass),
        scaled_distance: round(scaled),
        overpressure_kpa: round(overpressureFromScaledDistance(scaled)),
      };
    }
    if (name === "multi_energy") {
      const mass = positive(inputs.fuel_mass_kg, "fuel_mass_kg");
      const heat = positive(inputs.heat_of_combustion_kj_kg, "heat_of_combustion_kj_kg");
      const blastStrength = Number(inputs.blast_strength ?? 5);
      const distance = positive(inputs.distance_m, "distance_m");
      const equivalentEnergy = (mass * heat * blastStrength) / 10;
      const equivalentTnt = equivalentEnergy / 4680;
      const scaled = distance / Math.pow(Math.max(equivalentTnt, 1e-6), 1 / 3);
      return {
        model_type: "multi_energy",
        equivalent_tnt_kg: round(equivalentTnt),
        scaled_distance: round(scaled),
        overpressure_kpa: round(overpressureFromScaledDistance(scaled) * (blastStrength / 5)),
      };
    }
    if (name === "vce") {
      const cloudMass = positive(inputs.cloud_mass_kg, "cloud_mass_kg");
      const heat = positive(inputs.heat_of_combustion_kj_kg, "heat_of_combustion_kj_kg");
      const delay = positive(inputs.ignition_delay_s, "ignition_delay_s");
      const congestion = Number(inputs.congestion_factor ?? 1);
      const distance = positive(inputs.distance_m, "distance_m");
      const yieldFactor = Math.min(0.3, 0.03 + 0.005 * delay + 0.05 * congestion);
      const tntMass = (cloudMass * heat * yieldFactor) / 4680;
      const scaled = distance / Math.pow(Math.max(tntMass, 1e-6), 1 / 3);
      return {
        model_type: "vce",
        yield_factor: round(yieldFactor),
        tnt_equivalent_mass_kg: round(tntMass),
        scaled_distance: round(scaled),
        overpressure_kpa: round(overpressureFromScaledDistance(scaled)),
      };
    }
    throw error("Unsupported fire/explosion model.");
  }

  function populationDistribution(inputs) {
    if (Array.isArray(inputs.population_distribution) && inputs.population_distribution.length > 0) {
      return inputs.population_distribution.map((item, index) => ({
        id: item.id || `zone-${index + 1}`,
        label: item.label || `Zone ${index + 1}`,
        population: positive(item.population, "population"),
        ...item,
      }));
    }
    if (inputs.population_count != null && Number(inputs.population_count) > 0) {
      return [{ id: "population", label: "Population", population: Number(inputs.population_count) }];
    }
    return [];
  }

  function summarizePopulation(records, probabilityKey, casesKey, evaluator) {
    let populationTotal = 0;
    let expectedCases = 0;
    let maxProbability = 0;
    const populationResults = records.map((record) => {
      const result = evaluator(record);
      const probability = Number(result[probabilityKey]);
      const expected = probability * Number(record.population);
      populationTotal += Number(record.population);
      expectedCases += expected;
      maxProbability = Math.max(maxProbability, probability);
      return {
        id: record.id,
        label: record.label,
        population: round(record.population),
        ...result,
        [casesKey]: round(expected),
      };
    });
    return {
      population_results: populationResults,
      population_total: round(populationTotal),
      [casesKey]: round(expectedCases),
      maximum_probability: round(maxProbability),
    };
  }

  function curveValues(inputs, listKey, minKey, maxKey) {
    if (Array.isArray(inputs[listKey]) && inputs[listKey].length > 0) {
      return inputs[listKey].map((item) => positive(item, listKey));
    }
    const min = positive(inputs[minKey], minKey);
    const max = positive(inputs[maxKey], maxKey);
    const points = Math.max(2, Number(inputs.points ?? 9));
    const step = (max - min) / (points - 1);
    return Array.from({ length: points }, (_, index) => min + step * index);
  }

  function solveEffectModel(modelType, inputs) {
    const name = String(modelType).toLowerCase();
    if (name === "toxic_probit") {
      const concentration = positive(inputs.concentration_kg_m3, "concentration_kg_m3");
      const exposure = positive(inputs.exposure_time_s ?? inputs.exposure_duration_s, "exposure_time_s");
      const a = Number(inputs.a ?? -14.3);
      const b = Number(inputs.b ?? 2.3);
      const n = Number(inputs.n ?? 2.0);
      const toxicLoad = Math.pow(concentration, n) * exposure;
      const probit = a + b * Math.log(toxicLoad);
      const fatalityProbability = probitProbability(probit);
      return {
        model_type: "toxic_probit",
        probit: round(probit),
        fatality_probability: round(fatalityProbability),
        toxic_load: round(toxicLoad),
        ...summarizePopulation(populationDistribution(inputs), "fatality_probability", "expected_fatalities", (record) =>
          solveEffectModel("toxic_probit", {
            concentration_kg_m3: record.concentration_kg_m3 ?? concentration,
            exposure_duration_s: record.exposure_duration_s ?? record.exposure_time_s ?? exposure,
            a,
            b,
            n,
          })),
      };
    }
    if (name === "toxic_dose_response") {
      const exposure = positive(inputs.exposure_time_s ?? inputs.exposure_duration_s, "exposure_time_s");
      const a = Number(inputs.a ?? -14.3);
      const b = Number(inputs.b ?? 2.3);
      const n = Number(inputs.n ?? 2.0);
      return {
        model_type: "toxic_dose_response",
        exposure_time_s: round(exposure),
        curve: curveValues(inputs, "concentrations_kg_m3", "min_concentration_kg_m3", "max_concentration_kg_m3").map((value) => {
          const result = solveEffectModel("toxic_probit", {
            concentration_kg_m3: value,
            exposure_time_s: exposure,
            a,
            b,
            n,
          });
          return {
            concentration_kg_m3: round(value),
            probit: result.probit,
            fatality_probability: result.fatality_probability,
            toxic_load: result.toxic_load,
          };
        }),
      };
    }
    if (name === "thermal_probit") {
      const heatFlux = positive(inputs.heat_flux_kw_m2 ?? inputs.radiation_kw_m2, "heat_flux_kw_m2");
      const exposure = positive(inputs.exposure_time_s ?? inputs.exposure_duration_s, "exposure_time_s");
      const a = Number(inputs.a ?? -36.38);
      const b = Number(inputs.b ?? 2.56);
      const thermalLoad = Math.pow(heatFlux, 4 / 3) * exposure;
      const probit = a + b * Math.log(thermalLoad);
      const burnProbability = probitProbability(probit);
      return {
        model_type: "thermal_probit",
        probit: round(probit),
        burn_probability: round(burnProbability),
        thermal_load: round(thermalLoad),
        ...summarizePopulation(populationDistribution(inputs), "burn_probability", "expected_burn_cases", (record) =>
          solveEffectModel("thermal_probit", {
            heat_flux_kw_m2: record.heat_flux_kw_m2 ?? record.radiation_kw_m2 ?? heatFlux,
            exposure_duration_s: record.exposure_duration_s ?? record.exposure_time_s ?? exposure,
            a,
            b,
          })),
      };
    }
    if (name === "thermal_dose_response") {
      const exposure = positive(inputs.exposure_time_s ?? inputs.exposure_duration_s, "exposure_time_s");
      const a = Number(inputs.a ?? -36.38);
      const b = Number(inputs.b ?? 2.56);
      return {
        model_type: "thermal_dose_response",
        exposure_time_s: round(exposure),
        curve: curveValues(inputs, "heat_fluxes_kw_m2", "min_heat_flux_kw_m2", "max_heat_flux_kw_m2").map((value) => {
          const result = solveEffectModel("thermal_probit", {
            heat_flux_kw_m2: value,
            exposure_time_s: exposure,
            a,
            b,
          });
          return {
            heat_flux_kw_m2: round(value),
            probit: result.probit,
            burn_probability: result.burn_probability,
            thermal_load: result.thermal_load,
          };
        }),
      };
    }
    if (name === "explosion_probit") {
      const overpressure = positive(inputs.overpressure_kpa, "overpressure_kpa");
      const a = Number(inputs.a ?? -77.1);
      const b = Number(inputs.b ?? 6.91);
      const probit = a + b * Math.log(overpressure * 1000);
      const fatalityProbability = probitProbability(probit);
      return {
        model_type: "explosion_probit",
        probit: round(probit),
        fatality_probability: round(fatalityProbability),
        ...summarizePopulation(populationDistribution(inputs), "fatality_probability", "expected_fatalities", (record) =>
          solveEffectModel("explosion_probit", {
            overpressure_kpa: record.overpressure_kpa ?? overpressure,
            a,
            b,
          })),
      };
    }
    if (name === "explosion_dose_response") {
      const a = Number(inputs.a ?? -77.1);
      const b = Number(inputs.b ?? 6.91);
      return {
        model_type: "explosion_dose_response",
        curve: curveValues(inputs, "overpressures_kpa", "min_overpressure_kpa", "max_overpressure_kpa").map((value) => {
          const result = solveEffectModel("explosion_probit", {
            overpressure_kpa: value,
            a,
            b,
          });
          return {
            overpressure_kpa: round(value),
            probit: result.probit,
            fatality_probability: result.fatality_probability,
          };
        }),
      };
    }
    throw error("Unsupported effect model.");
  }

  function lookupToxicCriteria(inputs) {
    const chemical = String(inputs.chemical || "").trim().toLowerCase().replace(/ /g, "_");
    if (!chemical) {
      throw error("Provide 'chemical' for toxic criteria lookup.");
    }
    const registry = {
      chlorine: {
        units: "ppm",
        aegl_1: 0.5,
        aegl_2: 2.8,
        aegl_3: 50.0,
        erpg_1: 1.0,
        erpg_2: 3.0,
        erpg_3: 20.0,
        idlh: 10.0,
        tlv_twa: 0.5,
        pel_twa: 1.0,
        toxic_endpoint: 3.0,
      },
      ammonia: {
        units: "ppm",
        aegl_1: 30.0,
        aegl_2: 160.0,
        aegl_3: 1100.0,
        erpg_1: 25.0,
        erpg_2: 150.0,
        erpg_3: 750.0,
        idlh: 300.0,
        tlv_twa: 25.0,
        pel_twa: 50.0,
        toxic_endpoint: 150.0,
      },
      hydrogen_sulfide: {
        units: "ppm",
        aegl_1: 0.75,
        aegl_2: 41.0,
        aegl_3: 76.0,
        erpg_1: 0.1,
        erpg_2: 30.0,
        erpg_3: 100.0,
        idlh: 100.0,
        tlv_twa: 1.0,
        pel_twa: 20.0,
        toxic_endpoint: 30.0,
      },
      sulfur_dioxide: {
        units: "ppm",
        aegl_1: 0.2,
        aegl_2: 0.75,
        aegl_3: 30.0,
        erpg_1: 0.3,
        erpg_2: 3.0,
        erpg_3: 15.0,
        idlh: 100.0,
        tlv_twa: 0.25,
        pel_twa: 5.0,
        toxic_endpoint: 3.0,
      },
      ...(inputs.criteria_overrides || {}),
    };
    if (!registry[chemical]) {
      throw error(`Chemical '${chemical}' is not in the starter toxic criteria registry.`);
    }
    const entry = registry[chemical];
    const criteriaNames =
      Array.isArray(inputs.criteria_names) && inputs.criteria_names.length > 0
        ? inputs.criteria_names
        : ["aegl_1", "aegl_2", "aegl_3", "erpg_1", "erpg_2", "erpg_3", "idlh", "tlv_twa", "pel_twa", "toxic_endpoint"];
    const criteria = {};
    criteriaNames.forEach((name) => {
      const key = String(name).toLowerCase();
      if (entry[key] == null) {
        throw error(`Criterion '${key}' is not available for chemical '${chemical}'.`);
      }
      criteria[key] = Number(entry[key]);
    });
    return {
      model_type: "toxic_criteria_lookup",
      chemical,
      units: entry.units || "ppm",
      criteria,
      available_criteria: Object.keys(entry).filter((key) => key !== "units").sort(),
      notes: [
        "The built-in registry is a starter dataset intended for API integration and extension.",
        "Use criteria_overrides to inject organization-specific or updated toxic criteria values.",
      ],
    };
  }

  function solvePreventionResponseModel(modelType, inputs) {
    const name = String(modelType).toLowerCase();
    if (name === "fire_triangle_screening") {
      const missing = [];
      if (!inputs.fuel_present) missing.push("fuel");
      if (!inputs.oxidizer_present) missing.push("oxidizer");
      if (!inputs.ignition_source_present) missing.push("ignition_source");
      return {
        model_type: "fire_triangle_screening",
        triangle_complete: Boolean(inputs.fuel_present && inputs.oxidizer_present && inputs.ignition_source_present),
        missing_elements: missing,
      };
    }
    if (name === "autoignition_screening") {
      const processTemperature = positive(inputs.process_temperature_c, "process_temperature_c");
      const autoignitionTemperature = positive(inputs.autoignition_temperature_c, "autoignition_temperature_c");
      const safetyMargin = autoignitionTemperature - processTemperature;
      return {
        model_type: "autoignition_screening",
        safety_margin_c: round(safetyMargin),
        autoignition_risk: safetyMargin <= 0 ? "high" : safetyMargin < 50 ? "elevated" : "screened_low",
      };
    }
    if (name === "inerting_requirement") {
      const initialOxygen = positive(inputs.initial_oxygen_fraction, "initial_oxygen_fraction");
      const targetOxygen = positive(inputs.target_oxygen_fraction, "target_oxygen_fraction");
      const volume = positive(inputs.protected_volume_m3, "protected_volume_m3");
      const purity = Number(inputs.inert_gas_purity_fraction ?? 0.99);
      if (targetOxygen >= initialOxygen) {
        throw error("Input 'target_oxygen_fraction' must be lower than 'initial_oxygen_fraction'.");
      }
      return {
        model_type: "inerting_requirement",
        oxygen_removed_fraction: round(initialOxygen - targetOxygen),
        inert_gas_required_m3: round((volume * (initialOxygen - targetOxygen)) / purity),
      };
    }
    if (name === "ignition_energy_screening") {
      const sourceEnergy = positive(inputs.source_energy_mj, "source_energy_mj");
      const mie = positive(inputs.minimum_ignition_energy_mj, "minimum_ignition_energy_mj");
      return {
        model_type: "ignition_energy_screening",
        energy_ratio: round(sourceEnergy / mie),
        ignition_likelihood: sourceEnergy / mie >= 1 ? "credible" : "screened_low",
      };
    }
    if (name === "spray_mist_screening") {
      const dropletSize = positive(inputs.droplet_size_microns, "droplet_size_microns");
      const flashPoint = positive(inputs.flash_point_c, "flash_point_c");
      const liquidTemperature = positive(inputs.liquid_temperature_c, "liquid_temperature_c");
      const sprayPressure = positive(inputs.spray_pressure_bar, "spray_pressure_bar");
      const atomizationFactor = sprayPressure / Math.max(dropletSize, 1);
      const mistEnhancement = atomizationFactor * Math.max(liquidTemperature / Math.max(flashPoint, 1), 0.1);
      return {
        model_type: "spray_mist_screening",
        atomization_factor: round(atomizationFactor),
        mist_enhancement_factor: round(mistEnhancement),
        mist_fire_risk: mistEnhancement >= 1 ? "elevated" : "screened_low",
      };
    }
    if (name === "release_prevention_screening") {
      const barriers = positive(inputs.barrier_count, "barrier_count");
      const detectionTime = positive(inputs.detection_time_s, "detection_time_s");
      const isolationTime = positive(inputs.isolation_time_s, "isolation_time_s");
      const inspectionInterval = positive(inputs.inspection_interval_days, "inspection_interval_days");
      const shutdownProbability = Number(inputs.shutdown_success_probability ?? 0.9);
      const preventionScore =
        (barriers * shutdownProbability) / (1 + detectionTime / 60 + isolationTime / 60) * (30 / inspectionInterval);
      return {
        model_type: "release_prevention_screening",
        prevention_score: round(preventionScore),
        barrier_health_factor: round(30 / inspectionInterval),
        screening_assessment: preventionScore >= 1 ? "strong" : "needs_attention",
      };
    }
    if (name === "emergency_response_planning") {
      const population = positive(inputs.population_exposed, "population_exposed");
      const responseTime = positive(inputs.response_team_time_s, "response_team_time_s");
      const shelterTime = positive(inputs.shelter_in_place_time_s, "shelter_in_place_time_s");
      const evacuationTime = positive(inputs.evacuation_time_s, "evacuation_time_s");
      const releaseDuration = positive(inputs.release_duration_s, "release_duration_s");
      return {
        model_type: "emergency_response_planning",
        preferred_action: shelterTime <= evacuationTime ? "shelter_in_place" : "evacuate",
        urgency_score: round((population * releaseDuration) / responseTime),
        response_window_s: round(Math.min(shelterTime, evacuationTime)),
      };
    }
    throw error("Unsupported prevention/response model.");
  }

  function solveVisualization(layerType, inputs) {
    const name = String(layerType).toLowerCase();
    if (name === "plume_map") {
      const gridDistances = inputs.grid_distances_m ?? [50, 100, 200, 400, 800];
      return {
        layer_type: "plume_map",
        source: inputs.source,
        grid: gridDistances.map((distance) => ({
          distance_m: distance,
          concentration_kg_m3: solveDispersionModel("gaussian_plume", {
            release_rate_kg_s: inputs.release_rate_kg_s,
            wind_speed_m_s: inputs.wind_speed_m_s,
            x_m: distance,
            y_m: 0,
            z_m: inputs.z_m ?? 0,
            release_height_m: inputs.release_height_m ?? 0,
            stability_class: inputs.stability_class ?? "D",
          }).concentration_kg_m3,
        })),
      };
    }
    if (name === "heatmap") {
      const xDistances = inputs.x_distances_m ?? [50, 100, 200, 400, 800];
      const yOffsets = inputs.y_offsets_m ?? [-200, -100, -50, 0, 50, 100, 200];
      const points = [];
      xDistances.forEach((distance) => {
        yOffsets.forEach((offset) => {
          points.push({
            x_m: distance,
            y_m: offset,
            concentration_kg_m3: solveDispersionModel("gaussian_plume", {
              release_rate_kg_s: inputs.release_rate_kg_s,
              wind_speed_m_s: inputs.wind_speed_m_s,
              x_m: distance,
              y_m: offset,
              z_m: inputs.z_m ?? 0,
              release_height_m: inputs.release_height_m ?? 0,
              stability_class: inputs.stability_class ?? "D",
            }).concentration_kg_m3,
          });
        });
      });
      return { layer_type: "heatmap", source: inputs.source, points };
    }
    if (name === "risk_contours") {
      const features = [
        pointFeature(inputs.source.latitude, inputs.source.longitude, {
          role: "source",
          label: inputs.source.label || "Source",
        }),
      ];
      (inputs.zones ?? []).forEach((zone) => {
        features.push(
          circlePolygon(inputs.source.latitude, inputs.source.longitude, Number(zone.radius_m), {
            role: "risk_contour",
            scenario_type: inputs.scenario_type || "fire",
            label: zone.label,
            threshold: zone.threshold,
            unit: zone.unit,
            radius_m: zone.radius_m,
          }),
        );
      });
      return { layer_type: "risk_contours", geojson: { type: "FeatureCollection", features } };
    }
    if (name === "time_evolution") {
      const steps = Math.max(1, Number(inputs.steps ?? 5));
      const maxRadius = Number(inputs.max_radius_m ?? 500);
      const frameInterval = Number(inputs.frame_interval_s ?? 60);
      return {
        layer_type: "time_evolution",
        frames: Array.from({ length: steps }, (_, index) => {
          const radius = (maxRadius * (index + 1)) / steps;
          return {
            time_s: frameInterval * (index + 1),
            radius_m: round(radius),
            feature: circlePolygon(inputs.source.latitude, inputs.source.longitude, radius, {
              role: "time_frame",
              frame_index: index + 1,
              time_s: frameInterval * (index + 1),
              radius_m: round(radius),
            }),
          };
        }),
      };
    }
    throw error("Unsupported visualization layer.");
  }

  function haversineDistanceM(lat1, lon1, lat2, lon2) {
    const toRadians = (degrees) => (degrees * PI) / 180;
    const radius = 6371000;
    const dLat = toRadians(lat2 - lat1);
    const dLon = toRadians(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * radius * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  function pointFeature(latitude, longitude, properties) {
    return {
      type: "Feature",
      properties,
      geometry: { type: "Point", coordinates: [longitude, latitude] },
    };
  }

  function circlePolygon(latitude, longitude, radiusM, properties) {
    const coordinates = [];
    const earthRadius = 6371000;
    for (let index = 0; index <= 64; index += 1) {
      const bearing = (2 * PI * index) / 64;
      const lat1 = (latitude * PI) / 180;
      const lon1 = (longitude * PI) / 180;
      const lat2 = Math.asin(
        Math.sin(lat1) * Math.cos(radiusM / earthRadius) +
          Math.cos(lat1) * Math.sin(radiusM / earthRadius) * Math.cos(bearing),
      );
      const lon2 =
        lon1 +
        Math.atan2(
          Math.sin(bearing) * Math.sin(radiusM / earthRadius) * Math.cos(lat1),
          Math.cos(radiusM / earthRadius) - Math.sin(lat1) * Math.sin(lat2),
        );
      coordinates.push([(lon2 * 180) / PI, (lat2 * 180) / PI]);
    }
    return {
      type: "Feature",
      properties,
      geometry: { type: "Polygon", coordinates: [coordinates] },
    };
  }

  function calculateModel(modelId, inputs, constantOverrides) {
    const constants = resolveConstants(modelId, constantOverrides);
    if (modelId === "dispersion.gaussian_puff_ground") {
      return {
        outputs: {
          concentration: round(
            puffDispersionGround({
              Q: inputs.Q,
              y: inputs.y ?? 0,
              z: inputs.z ?? 0,
              sigma_y: inputs.sigma_y,
              sigma_z: inputs.sigma_z,
            }),
          ),
        },
        constants,
      };
    }
    if (modelId === "dispersion.gaussian_puff_screening_radius") {
      const releasedMass = positive(inputs.released_mass_kg, "released_mass_kg");
      const threshold = positive(inputs.concentration_threshold_kg_m3, "concentration_threshold_kg_m3");
      const stability = String(inputs.stability_class ?? "D").toUpperCase();
      let radius = 0;
      for (let distance = 1; distance <= 100000; distance += 25) {
        const concentration = puffDispersionGround({
          Q: releasedMass,
          y: Number(inputs.y ?? 0),
          z: Number(inputs.z ?? 0),
          sigma_y: sigmaY(distance, stability),
          sigma_z: sigmaZ(distance, stability),
        });
        if (concentration <= threshold) {
          radius = distance;
          break;
        }
      }
      radius = radius || 100000;
      return {
        outputs: {
          impact_radius_m: round(radius),
          impact_area_m2: round(PI * radius * radius),
          screening_release_mass_kg: round(releasedMass),
        },
        constants,
      };
    }
    if (modelId === "dispersion.pasquill_gifford_sigma_y") {
      const x = positive(inputs.x, "x");
      const stability = String(inputs.stability_class ?? "D").toUpperCase();
      return {
        outputs: {
          sigma_y: round(sigmaY(x, stability)),
          sigma_z_screening: round(sigmaZ(x, stability)),
        },
        constants,
      };
    }
    if (modelId === "fire.flammability_limits") {
      return { outputs: flammabilityLimits(inputs, constants), constants };
    }
    if (modelId === "fire.point_source_heat_flux") {
      return { outputs: pointSourceHeatFlux(inputs, constants), constants };
    }
    if (modelId === "fire.point_source_heat_flux_radius") {
      return { outputs: pointSourceHeatFluxRadius(inputs, constants), constants };
    }
    if (MODEL_DETAILS[modelId] && MODEL_DETAILS[modelId].status === "planned") {
      throw error("Model not implemented.", 501);
    }
    throw error("Model not found.", 404);
  }

  function buildScenarioDefinition(payload) {
    const classification = String(payload.classification).toLowerCase();
    const incidentType = String(payload.incident_type).toLowerCase();
    const scenario = {
      incident_type: incidentType,
      classification,
      inventory: payload.inventory ?? {},
      equipment: payload.equipment ?? {},
      failure_mode: payload.failure_mode ?? null,
      meteorology: { ...(payload.meteorology ?? {}) },
      release_height_m: payload.release_height_m ?? null,
      topography: payload.topography ?? "rural",
      release_duration_s: payload.release_duration_s ?? null,
      conservative_mode: Boolean(payload.conservative_mode),
      references: ["Worst-case screening defaults use a 10-minute release, ground-level release, 1.5 m/s wind, and F stability when applicable."],
    };
    if (classification === "worst_case") {
      scenario.release_duration_s = payload.release_duration_s ?? 600;
      scenario.release_height_m = payload.release_height_m ?? 0;
      scenario.meteorology.wind_speed_m_s = scenario.meteorology.wind_speed_m_s ?? 1.5;
      scenario.meteorology.stability_class = scenario.meteorology.stability_class ?? "F";
      scenario.meteorology.temperature_c = scenario.meteorology.temperature_c ?? 25;
    }
    return scenario;
  }

  function buildImpactReleasedMass(asset) {
    if (asset.released_mass_kg != null) {
      return Number(asset.released_mass_kg);
    }
    const leakDuration = asset.duration_s ?? asset.leak_duration_s;
    if (asset.mass_flow_kg_s != null && leakDuration != null) {
      return Number(asset.mass_flow_kg_s) * Number(leakDuration);
    }
    if (
      leakDuration != null &&
      (asset.upstream_pressure_pa != null || asset.line_pressure_kpa != null || asset.delta_pressure_pa != null || asset.density_kg_m3 != null)
    ) {
      if (asset.density_kg_m3 != null && (asset.liquid_head_m != null || asset.delta_pressure_pa != null)) {
        return solveSourceModel("liquid_release", {
          density_kg_m3: asset.density_kg_m3,
          duration_s: leakDuration,
          source_subtype: asset.source_subtype ?? "hole_in_tank",
          discharge_coefficient: asset.discharge_coefficient ?? 0.62,
          liquid_head_m: asset.liquid_head_m,
          delta_pressure_pa: asset.delta_pressure_pa,
          hole_area_m2: asset.hole_area_m2,
          hole_diameter_m: asset.hole_diameter_m ?? asset.diameter_m,
          pipe_area_m2: asset.pipe_area_m2,
          pipe_diameter_m: asset.pipe_diameter_m ?? asset.diameter_m,
          pipe_length_m: asset.pipe_length_m,
          inventory_mass_kg: asset.inventory_mass_kg,
          conservative_mode: asset.conservative_mode ?? false,
        }).total_mass_kg;
      }
      return solveSourceModel("gas_release", {
        duration_s: leakDuration,
        upstream_pressure_pa: asset.upstream_pressure_pa ?? Number(asset.line_pressure_kpa ?? 0) * 1000,
        downstream_pressure_pa: asset.downstream_pressure_pa ?? 101325,
        temperature_k: asset.temperature_k ?? Number(asset.gas_temperature_c ?? 15) + 273.15,
        heat_capacity_ratio: asset.heat_capacity_ratio ?? 1.3,
        molecular_weight_kg_kmol: asset.molecular_weight_kg_kmol ?? 28.97,
        discharge_coefficient: asset.discharge_coefficient ?? 0.62,
        compressibility: asset.compressibility ?? 1.0,
        source_subtype: asset.source_subtype ?? asset.discharge_geometry ?? "pipe",
        pipe_area_m2: asset.pipe_area_m2,
        pipe_diameter_m: asset.pipe_diameter_m ?? asset.diameter_m,
        pipe_length_m: asset.pipe_length_m,
        hole_area_m2: asset.hole_area_m2,
        hole_diameter_m: asset.hole_diameter_m ?? asset.diameter_m,
        inventory_mass_kg: asset.inventory_mass_kg,
        vessel_volume_m3: asset.vessel_volume_m3,
        conservative_mode: asset.conservative_mode ?? false,
      }).total_mass_kg;
    }
    throw error(
      "Leak impact zones require either 'released_mass_kg', source-term inputs, or both 'mass_flow_kg_s' and 'leak_duration_s'.",
    );
  }

  function serviceResponse(modelType, outputs, catalog) {
    const metadata = catalog.find((item) => item.model_type === modelType) || {
      equations: [],
      assumptions: [],
      constants: [],
      references: [],
    };
    return {
      model_type: modelType,
      outputs,
      equations: metadata.equations,
      assumptions: metadata.assumptions,
      constants: metadata.constants,
      references: metadata.references,
    };
  }

  function analyzeSign(payload) {
    const observedText = String(payload.observed_text || "").trim();
    const siteContext = String(payload.site_context || "").trim();
    const combinedText = `${observedText} ${siteContext}`.trim().toLowerCase();
    if (!combinedText) {
      throw error("Provide sign text in 'observed_text' or an OCR result to analyze the sign.");
    }

    const patterns = [
      {
        sign_type: "gas_pipeline",
        keywords: ["gas pipeline", "gas line", "natural gas", "buried gas line", "gasleitung", "gazoduc"],
        asset_type: "pipeline",
        substance_family: "gas",
        hazard_classes: ["release", "dispersion"],
        scenario_template_id: "pipeline_leak",
      },
      {
        sign_type: "high_pressure_gas",
        keywords: ["high pressure gas", "gas under pressure", "pressurized gas", "alta presion", "haute pression"],
        asset_type: "pipeline",
        substance_family: "pressurized_gas",
        hazard_classes: ["release", "dispersion", "jet_fire"],
        scenario_template_id: "pipeline_leak",
      },
      {
        sign_type: "flammable_gas",
        keywords: ["flammable gas", "flammable", "lpg", "lng", "hydrogen", "gaz inflammable"],
        asset_type: "gas_system",
        substance_family: "flammable_gas",
        hazard_classes: ["release", "dispersion", "jet_fire", "explosion"],
        scenario_template_id: "pipeline_leak",
      },
      {
        sign_type: "toxic_gas",
        keywords: ["toxic gas", "poison gas", "chlorine", "ammonia", "h2s", "hydrogen sulfide"],
        asset_type: "gas_system",
        substance_family: "toxic_gas",
        hazard_classes: ["release", "dispersion", "toxic_effects"],
        scenario_template_id: "pipeline_leak",
      },
    ];

    let best = null;
    patterns.forEach((pattern) => {
      const matchedTerms = pattern.keywords.filter((term) => combinedText.includes(term));
      if (matchedTerms.length > 0) {
        const candidate = { ...pattern, matched_terms: matchedTerms, confidence: matchedTerms.length / pattern.keywords.length };
        if (!best || candidate.confidence > best.confidence) {
          best = candidate;
        }
      }
    });

    const result = best || {
      sign_type: "unknown_gas_sign",
      matched_terms: [],
      confidence: combinedText.includes("gas") ? 0.15 : 0.05,
      asset_type: combinedText.includes("pipeline") || combinedText.includes("line") ? "pipeline" : "gas_system",
      substance_family: "gas",
      hazard_classes: ["release", "dispersion"],
      scenario_template_id: "pipeline_leak",
    };

    return {
      sign_type: result.sign_type,
      confidence: round(result.confidence),
      normalized_text: combinedText.replace(/\s+/g, " ").trim(),
      matched_terms: result.matched_terms,
      asset_type: result.asset_type,
      substance_family: result.substance_family,
      hazard_classes: result.hazard_classes,
      recommended_services: ["scenario_engine", "source_models", "dispersion_models", "visualization"].concat(
        result.hazard_classes.includes("jet_fire") || result.hazard_classes.includes("explosion") ? ["fire_explosion_models"] : [],
      ).concat(
        result.hazard_classes.includes("toxic_effects") || result.hazard_classes.includes("jet_fire") || result.hazard_classes.includes("explosion") ? ["effect_models"] : [],
      ),
      recommended_models: {
        source_model: "gas_release",
        dispersion_model: "gaussian_puff",
        impact_endpoint: "/gis/impact-zones",
        scenario_endpoint: "/scenarios",
      },
      scenario_template_id: result.scenario_template_id,
      scenario_definition_seed: {
        incident_type: "pipe_rupture",
        classification: "realistic_case",
        inventory: { phase: "gas" },
        equipment: { type: result.asset_type },
        failure_mode: "leak",
        topography: payload.topography || "urban",
      },
      impact_zone_seed: {
        scenario_type: "leak",
        asset: {
          stability_class: payload.stability_class || "D",
          wind_speed_m_s: payload.wind_speed_m_s || 3.0,
          gas_temperature_c: null,
          line_pressure_kpa: null,
          diameter_m: null,
          hole_diameter_m: null,
          leak_duration_s: 300,
        },
        criteria: [{ label: "Concern threshold", threshold: 0.02, unit: "kg/m^3" }],
      },
      required_parameters: [
        { name: "line_pressure_kpa", type: "number", description: "Internal line pressure at the sign location.", unit: "kPa" },
        { name: "gas_temperature_c", type: "number", description: "Gas temperature at release conditions.", unit: "degC" },
        { name: "diameter_m", type: "number", description: "Pipeline or nozzle diameter used for source-term calculations.", unit: "m" },
        { name: "hole_diameter_m", type: "number", description: "Estimated leak opening diameter.", unit: "m" },
        { name: "leak_duration_s", type: "number", description: "Estimated duration before isolation or depletion.", unit: "s" },
        { name: "stability_class", type: "string", description: "Pasquill stability class for dispersion screening.", unit: null },
        { name: "wind_speed_m_s", type: "number", description: "Wind speed for dispersion screening.", unit: "m/s" },
      ],
      notes: [
        "This browser-local endpoint classifies the sign from OCR text or manually entered sign text.",
        "For photo workflows, extract OCR text in the client and send it through observed_text.",
      ],
    };
  }

  function route(method, rawPath, body) {
    const path = new URL(rawPath, "http://browser.local");
    const payload = body ?? {};
    if (method === "GET" && path.pathname === "/") {
      return {
        service: "DeepSafety Consequence Analysis API",
        version: "0.1.0",
        docs: "./api-docs.html",
        runtime: "browser-local",
      };
    }
    if (method === "GET" && path.pathname === "/health") {
      return { status: "ok" };
    }
    if (method === "GET" && path.pathname === "/models") {
      const includePlanned = path.searchParams.get("include_planned") !== "false";
      return Object.values(MODEL_DETAILS)
        .filter((item) => includePlanned || item.status !== "planned")
        .map(summary);
    }
    if (method === "GET" && path.pathname.startsWith("/models/")) {
      const modelId = decodeURIComponent(path.pathname.replace("/models/", ""));
      const model = MODEL_DETAILS[modelId];
      if (!model) {
        throw error("Model not found.", 404);
      }
      return model;
    }
    if (method === "POST" && path.pathname.startsWith("/models/") && path.pathname.endsWith("/calculate")) {
      const modelId = decodeURIComponent(path.pathname.replace("/models/", "").replace("/calculate", ""));
      const model = MODEL_DETAILS[modelId];
      if (!model) {
        throw error("Model not found.", 404);
      }
      const calculation = calculateModel(modelId, payload.inputs ?? {}, payload.constants ?? {});
      return {
        model: summary(model),
        inputs: payload.inputs ?? {},
        outputs: calculation.outputs,
        constants: calculation.constants,
        equations: model.equations,
        warnings: [],
      };
    }
    if (method === "GET" && path.pathname === "/constants") {
      return Object.entries(DEFAULT_CONSTANTS).map(([name, definition]) => ({ name, ...definition }));
    }
    if (method === "GET" && path.pathname.startsWith("/constants/")) {
      const modelId = decodeURIComponent(path.pathname.replace("/constants/", ""));
      if (!MODEL_DETAILS[modelId]) {
        throw error("Model not found.", 404);
      }
      return resolveConstants(modelId, {});
    }
    if (method === "GET" && path.pathname === "/scenario-catalog") {
      return SCENARIOS;
    }
    if (method === "GET" && path.pathname === "/scenarios") {
      return [];
    }
    if (method === "POST" && path.pathname === "/scenario-engine/define") {
      return { scenario: buildScenarioDefinition(payload) };
    }
    if (method === "GET" && path.pathname === "/scenario-library/templates") {
      return TEMPLATES;
    }
    if (method === "GET" && path.pathname === "/service-catalog") {
      return SERVICE_CATALOG;
    }
    if (method === "POST" && path.pathname === "/source-models/solve") {
      return serviceResponse(payload.model_type, solveSourceModel(payload.model_type, payload.inputs ?? {}), SERVICE_CATALOG.source_models);
    }
    if (method === "POST" && path.pathname === "/dispersion-models/solve") {
      return serviceResponse(payload.model_type, solveDispersionModel(payload.model_type, payload.inputs ?? {}), SERVICE_CATALOG.dispersion_models);
    }
    if (method === "POST" && path.pathname === "/fire-explosion-models/solve") {
      return serviceResponse(payload.model_type, solveFireExplosionModel(payload.model_type, payload.inputs ?? {}), SERVICE_CATALOG.fire_explosion_models);
    }
    if (method === "POST" && path.pathname === "/effect-models/solve") {
      return serviceResponse(payload.model_type, solveEffectModel(payload.model_type, payload.inputs ?? {}), SERVICE_CATALOG.effect_models);
    }
    if (method === "POST" && path.pathname === "/toxic-criteria/lookup") {
      return serviceResponse("toxic_criteria_lookup", lookupToxicCriteria(payload.inputs ?? {}), SERVICE_CATALOG.toxic_criteria);
    }
    if (method === "POST" && path.pathname === "/prevention-response-models/solve") {
      return serviceResponse(payload.model_type, solvePreventionResponseModel(payload.model_type, payload.inputs ?? {}), SERVICE_CATALOG.prevention_response_models);
    }
    if (method === "POST" && path.pathname === "/visualization/solve") {
      return { layer_type: payload.layer_type, payload: solveVisualization(payload.layer_type, payload.inputs ?? {}) };
    }
    if (method === "POST" && path.pathname === "/signs/analyze") {
      return analyzeSign(payload);
    }
    if (method === "POST" && path.pathname === "/gis/scenarios/evaluate") {
      const scenarioType = String(payload.scenario_type).toLowerCase();
      const modelId = payload.model_id || SCENARIOS[scenarioType]?.default_model_id;
      const model = MODEL_DETAILS[modelId];
      if (!model) {
        throw error("Model not found.", 404);
      }
      const source = payload.source;
      const receptors = payload.receptors ?? [];
      const features = [
        pointFeature(source.latitude, source.longitude, {
          role: "source",
          label: source.label || "Source",
          scenario_type: scenarioType,
        }),
      ];
      const results = receptors.map((receptor) => {
        const distance = haversineDistanceM(source.latitude, source.longitude, receptor.latitude, receptor.longitude);
        const baseInputs = payload.inputs ?? {};
        const outputs =
          modelId === "dispersion.gaussian_puff_ground"
            ? calculateModel(
                modelId,
                {
                  x: distance,
                  y: 0,
                  z: 0,
                  Q: baseInputs.Q ?? 25,
                  u: baseInputs.u ?? 3.5,
                  sigma_y: baseInputs.sigma_y ?? sigmaY(distance, baseInputs.stability_class ?? "D"),
                  sigma_z: baseInputs.sigma_z ?? sigmaZ(distance, baseInputs.stability_class ?? "D"),
                },
                payload.constants ?? {},
              ).outputs
            : calculateModel(
                modelId,
                {
                  distance_m: distance,
                  burning_rate_kg_s: baseInputs.burning_rate_kg_s,
                  heat_of_combustion_kj_kg: baseInputs.heat_of_combustion_kj_kg,
                },
                payload.constants ?? {},
              ).outputs;
        const result = {
          id: receptor.id,
          label: receptor.label || receptor.id,
          latitude: receptor.latitude,
          longitude: receptor.longitude,
          distance_m: round(distance, 3),
          outputs,
        };
        features.push(
          pointFeature(receptor.latitude, receptor.longitude, {
            role: "receptor",
            id: result.id,
            label: result.label,
            distance_m: result.distance_m,
            ...outputs,
          }),
        );
        return result;
      });
      return {
        scenario_type: scenarioType,
        model: summary(model),
        source,
        receptors: results,
        constants: resolveConstants(modelId, payload.constants ?? {}),
        equations: model.equations,
        geojson: { type: "FeatureCollection", features },
      };
    }
    if (method === "POST" && path.pathname === "/gis/impact-zones") {
      const scenarioType = String(payload.scenario_type).toLowerCase();
      const source = payload.source;
      const asset = payload.asset ?? {};
      const criteria = payload.criteria ?? [];
      const modelId = scenarioType === "fire" ? "fire.point_source_heat_flux_radius" : "dispersion.gaussian_puff_screening_radius";
      const model = MODEL_DETAILS[modelId];
      const features = [
        pointFeature(source.latitude, source.longitude, {
          role: "source",
          label: source.label || "Source",
          scenario_type: scenarioType,
          ...asset,
        }),
      ];
      const zones = criteria.map((criterion) => {
        const outputs =
          scenarioType === "fire"
            ? calculateModel(
                modelId,
                {
                  burning_rate_kg_s: asset.burning_rate_kg_s,
                  heat_of_combustion_kj_kg: asset.heat_of_combustion_kj_kg,
                  impact_threshold_kw_m2: criterion.threshold,
                },
                payload.constants ?? {},
              ).outputs
            : calculateModel(
                modelId,
                {
                  released_mass_kg: buildImpactReleasedMass(asset),
                  concentration_threshold_kg_m3: criterion.threshold,
                  stability_class: asset.stability_class ?? "D",
                  y: asset.y ?? 0,
                  z: asset.z ?? 0,
                },
                payload.constants ?? {},
              ).outputs;
        features.push(
          circlePolygon(source.latitude, source.longitude, Number(outputs.impact_radius_m), {
            role: "impact_zone",
            label: criterion.label,
            threshold: criterion.threshold,
            unit: criterion.unit,
            radius_m: outputs.impact_radius_m,
            area_m2: outputs.impact_area_m2,
            scenario_type: scenarioType,
          }),
        );
        return {
          label: criterion.label,
          threshold: criterion.threshold,
          unit: criterion.unit,
          radius_m: Number(outputs.impact_radius_m),
          area_m2: Number(outputs.impact_area_m2),
          outputs,
        };
      });
      return {
        scenario_type: scenarioType,
        source,
        asset,
        model: summary(model),
        zones,
        constants: resolveConstants(modelId, payload.constants ?? {}),
        equations: model.equations,
        geojson: { type: "FeatureCollection", features },
      };
    }
    throw error(`Unsupported browser-local route: ${path.pathname}`, 404);
  }

  window.DeepSafetyBrowserApi = {
    defaultBaseUrl: "browser://local",
    async request(method, path, payload) {
      try {
        return route(String(method).toUpperCase(), path, payload);
      } catch (issue) {
        const wrapped = new Error(issue instanceof Error ? issue.message : "Browser-local request failed.");
        wrapped.status = issue.status || 400;
        throw wrapped;
      }
    },
  };
})();
