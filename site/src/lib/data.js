// Readers for the JSON written by pipelines/build/site_data.py. Pages never compute numbers.
import fs from "node:fs";
import path from "node:path";

const dir = path.resolve(process.cwd(), "src/data/generated");
const read = (rel) => JSON.parse(fs.readFileSync(path.join(dir, rel), "utf8"));

export const site = () => read("site.json");
export const home = () => read("home.json");
export const catalogue = () => read("catalogue.json");
export const series = (id) => read(`series/${id}.json`);
export const latest = (s, how = "level") => {
  const pts = how === "level" ? s.data : s.transforms[how];
  return pts && pts.length ? { period: pts.at(-1)[0], value: pts.at(-1)[1] } : null;
};
export const valueAt = (s, how, period) => {
  const pts = how === "level" ? s.data : s.transforms[how];
  const hit = pts?.find((p) => p[0] === period);
  return hit ? hit[1] : null;
};
