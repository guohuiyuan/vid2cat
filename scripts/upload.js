const fs = require("fs");
const path = require("path");
const dotenv = require("dotenv");
const { PicGo } = require("picgo");

dotenv.config({ path: path.resolve(process.cwd(), ".env") });

const CONFIG_PATH = path.resolve(process.cwd(), "picgo.config.json");
const DEFAULT_REPO = "linbingwei/heikeson";
const DEFAULT_BRANCH = "master";
const DEFAULT_PATH = "images";

function printHelp() {
  console.log(
    "Usage:\n" +
      "  npm run upload -- <image-path> [more-image-paths]\n\n" +
      "Environment variables (.env or process env):\n" +
      "  GITEE_REPO=linbingwei/heikeson\n" +
      "  GITEE_BRANCH=master\n" +
      "  GITEE_PATH=images\n" +
      "  GITEE_TOKEN=your_gitee_personal_access_token\n" +
      "  GITEE_CUSTOM_URL=optional\n"
  );
}

function getEnv(name, fallback = "") {
  const value = process.env[name];
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function requireToken() {
  const token = getEnv("GITEE_TOKEN");
  if (!token) {
    console.error("Missing GITEE_TOKEN. Configure it in admin settings or .env first.");
    process.exit(1);
  }
  return token;
}

function collectInputFiles(argv) {
  const files = argv
    .filter((item) => item && !item.startsWith("--"))
    .map((item) => path.resolve(process.cwd(), item));

  if (files.length === 0) {
    printHelp();
    process.exit(1);
  }

  const missing = files.filter((file) => !fs.existsSync(file));
  if (missing.length > 0) {
    console.error("These files do not exist:");
    for (const file of missing) {
      console.error(`  ${file}`);
    }
    process.exit(1);
  }
  return files;
}

async function main() {
  if (process.argv.includes("--help") || process.argv.includes("-h")) {
    printHelp();
    return;
  }

  const files = collectInputFiles(process.argv.slice(2));
  const token = requireToken();
  const repo = getEnv("GITEE_REPO", DEFAULT_REPO);
  const branch = getEnv("GITEE_BRANCH", DEFAULT_BRANCH);
  const imagePath = getEnv("GITEE_PATH", DEFAULT_PATH);
  const customUrl = getEnv("GITEE_CUSTOM_URL", "");

  const picgo = new PicGo(CONFIG_PATH);
  picgo.setConfig({
    "picBed.current": "githubPlus",
    "picBed.uploader": "githubPlus",
    "picBed.githubPlus": {
      repo,
      branch,
      token,
      path: imagePath,
      customUrl,
      origin: "gitee"
    }
  });

  const result = await picgo.upload(files);
  if (!Array.isArray(result) || result.length === 0) {
    console.error("Upload finished, but PicGo did not return any result.");
    process.exit(1);
  }

  console.log("Upload successful:");
  for (const item of result) {
    console.log(`${item.fileName} -> ${item.imgUrl || ""}`);
  }
}

main().catch((error) => {
  console.error("Upload failed:");
  console.error(error && error.message ? error.message : error);
  process.exit(1);
});
