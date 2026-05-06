#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');

function nowIso() {
  return new Date().toISOString();
}

function parseArgs(argv) {
  const args = {
    industrialPlannerRoot: null,
    outputDir: path.join(projectRoot, 'src', 'adapters', 'industrial_planner'),
  };

  for (let index = 2; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--industrial-planner-root' || token === '--ip-root') {
      args.industrialPlannerRoot = argv[index + 1] ? path.resolve(argv[index + 1]) : null;
      index += 1;
      continue;
    }
    if (token === '--output-dir') {
      args.outputDir = argv[index + 1] ? path.resolve(argv[index + 1]) : args.outputDir;
      index += 1;
      continue;
    }
    if (token === '--help' || token === '-h') {
      printHelp();
      process.exit(0);
    }
    throw new Error(`Unknown argument: ${token}`);
  }

  if (!args.industrialPlannerRoot) {
    throw new Error('Missing required --industrial-planner-root argument');
  }
  return args;
}

function printHelp() {
  console.log(`Usage: node scripts/extract_ip_static_registry.mjs \\
  --industrial-planner-root /path/to/IndustrialPlanner-2 \\
  [--output-dir src/adapters/industrial_planner]`);
}

function resolveTsNodeLoader() {
  const globalRoot = execFileSync('npm', ['root', '-g'], { encoding: 'utf-8' }).trim();
  const loaderPath = path.join(globalRoot, 'ts-node', 'esm.mjs');
  if (!fs.existsSync(loaderPath)) {
    throw new Error(`Unable to locate ts-node ESM loader at ${loaderPath}`);
  }
  return loaderPath;
}

function extractRegistryPayload(industrialPlannerRoot) {
  const tempScriptPath = path.join(industrialPlannerRoot, `.tmp_extract_registry_${process.pid}_${Date.now()}.ts`);
  const probeSource = `
    import {
      ITEMS,
      RECIPES,
      DEVICE_TYPES,
      BASES,
      SOLID_ITEM_IDS,
      LIQUID_ITEM_IDS,
      BELT_TYPES,
      PIPE_TYPES,
      JUNCTION_TYPES,
      PIPE_JUNCTION_TYPES,
      HIDDEN_PLACEABLE_TYPE_IDS,
    } from './src/domain/registry.ts';

    const payload = {
      items: ITEMS,
      recipes: RECIPES,
      deviceTypes: DEVICE_TYPES,
      bases: BASES,
      solidItemIds: SOLID_ITEM_IDS,
      liquidItemIds: LIQUID_ITEM_IDS,
      beltTypeIds: Array.from(BELT_TYPES),
      pipeTypeIds: Array.from(PIPE_TYPES),
      junctionTypeIds: Array.from(JUNCTION_TYPES),
      pipeJunctionTypeIds: Array.from(PIPE_JUNCTION_TYPES),
      hiddenPlaceableTypeIds: Array.from(HIDDEN_PLACEABLE_TYPE_IDS),
    };

    console.log(JSON.stringify(payload));
  `;

  fs.writeFileSync(tempScriptPath, probeSource, 'utf-8');
  try {
    const loaderPath = resolveTsNodeLoader();
    const stdout = execFileSync(
      process.execPath,
      [
        '--experimental-specifier-resolution=node',
        '--loader',
        loaderPath,
        path.basename(tempScriptPath),
      ],
      {
        cwd: industrialPlannerRoot,
        encoding: 'utf-8',
        env: {
          ...process.env,
          TS_NODE_TRANSPILE_ONLY: '1',
          TS_NODE_COMPILER_OPTIONS: JSON.stringify({
            module: 'esnext',
            moduleResolution: 'bundler',
            allowImportingTsExtensions: true,
          }),
        },
      },
    );
    return JSON.parse(stdout.trim());
  } finally {
    try {
      fs.unlinkSync(tempScriptPath);
    } catch {
      // noop
    }
  }
}

function sortById(entries) {
  return [...entries].sort((left, right) => String(left.id).localeCompare(String(right.id)));
}

function dedupeSorted(values) {
  return [...new Set(values.map((value) => String(value)))].sort((left, right) => left.localeCompare(right));
}

function writeJson(filePath, payload) {
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf-8');
}

function main() {
  const args = parseArgs(process.argv);
  const industrialPlannerRoot = args.industrialPlannerRoot;
  if (!fs.existsSync(path.join(industrialPlannerRoot, 'src', 'domain', 'registry.ts'))) {
    throw new Error(`IndustrialPlanner registry.ts not found under ${industrialPlannerRoot}`);
  }
  fs.mkdirSync(args.outputDir, { recursive: true });

  const raw = extractRegistryPayload(industrialPlannerRoot);
  const generatedAt = nowIso();

  const deviceRegistry = {
    metadata: {
      source: 'IndustrialPlanner static registry snapshot',
      source_root_name: path.basename(industrialPlannerRoot),
      generated_at: generatedAt,
      device_type_count: Array.isArray(raw.deviceTypes) ? raw.deviceTypes.length : 0,
    },
    belt_type_ids: dedupeSorted(raw.beltTypeIds ?? []),
    pipe_type_ids: dedupeSorted(raw.pipeTypeIds ?? []),
    junction_type_ids: dedupeSorted(raw.junctionTypeIds ?? []),
    pipe_junction_type_ids: dedupeSorted(raw.pipeJunctionTypeIds ?? []),
    hidden_placeable_type_ids: dedupeSorted(raw.hiddenPlaceableTypeIds ?? []),
    warehouse_bus_type_ids: ['item_port_log_hongs_bus', 'item_port_log_hongs_bus_source'],
    device_types: sortById(raw.deviceTypes ?? []).map((entry) => ({
      ...entry,
      tags: Array.isArray(entry.tags) ? [...entry.tags] : [],
      ports0: Array.isArray(entry.ports0) ? entry.ports0 : [],
      placementConstraints: Array.isArray(entry.placementConstraints) ? entry.placementConstraints : [],
    })),
  };

  const baseRegistry = {
    metadata: {
      source: 'IndustrialPlanner static registry snapshot',
      source_root_name: path.basename(industrialPlannerRoot),
      generated_at: generatedAt,
      base_count: Array.isArray(raw.bases) ? raw.bases.length : 0,
    },
    bases: sortById(raw.bases ?? []).map((entry) => ({
      ...entry,
      tags: Array.isArray(entry.tags) ? [...entry.tags] : [],
      foundationBuildings: Array.isArray(entry.foundationBuildings) ? entry.foundationBuildings : [],
    })),
  };

  const recipeInputItemIds = dedupeSorted(
    (raw.recipes ?? []).flatMap((recipe) => (Array.isArray(recipe.inputs) ? recipe.inputs.map((entry) => entry.itemId) : [])),
  );
  const recipeOutputItemIds = dedupeSorted(
    (raw.recipes ?? []).flatMap((recipe) => (Array.isArray(recipe.outputs) ? recipe.outputs.map((entry) => entry.itemId) : [])),
  );

  const itemRegistry = {
    metadata: {
      source: 'IndustrialPlanner static registry snapshot',
      source_root_name: path.basename(industrialPlannerRoot),
      generated_at: generatedAt,
      item_count: Array.isArray(raw.items) ? raw.items.length : 0,
      recipe_count: Array.isArray(raw.recipes) ? raw.recipes.length : 0,
    },
    solid_item_ids: dedupeSorted(raw.solidItemIds ?? []),
    liquid_item_ids: dedupeSorted(raw.liquidItemIds ?? []),
    recipe_input_item_ids: recipeInputItemIds,
    recipe_output_item_ids: recipeOutputItemIds,
    items: sortById(raw.items ?? []).map((entry) => ({
      ...entry,
      tags: Array.isArray(entry.tags) ? [...entry.tags] : [],
    })),
    recipes: sortById(raw.recipes ?? []).map((entry) => ({
      ...entry,
      inputs: Array.isArray(entry.inputs) ? entry.inputs : [],
      outputs: Array.isArray(entry.outputs) ? entry.outputs : [],
      tags: Array.isArray(entry.tags) ? [...entry.tags] : [],
    })),
  };

  writeJson(path.join(args.outputDir, 'device_type_registry.json'), deviceRegistry);
  writeJson(path.join(args.outputDir, 'base_registry.json'), baseRegistry);
  writeJson(path.join(args.outputDir, 'item_registry.json'), itemRegistry);

  console.log(`Wrote device_type_registry.json, base_registry.json, and item_registry.json to ${args.outputDir}`);
}

try {
  main();
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
