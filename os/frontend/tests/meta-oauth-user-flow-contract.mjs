import fs from "node:fs";

const callback = fs.readFileSync(new URL("../src/pages/PlatformOAuthCallback.jsx", import.meta.url), "utf8");
const api = fs.readFileSync(new URL("../src/api.js", import.meta.url), "utf8");

for (const token of ["result?.status === \"connected\"", "result?.status === \"authorized\"", "授权成功，下一步请选择要绑定的 Meta 资源。", "返回平台账号"]) {
  if (!callback.includes(token)) throw new Error(`missing callback contract: ${token}`);
}
for (const token of ["getMetaResources", "getMetaBinding", "bindMetaResource", "/oauth/meta/resources/", "/oauth/meta/binding/", "/oauth/meta/bind/"]) {
  if (!api.includes(token)) throw new Error(`missing Meta API contract: ${token}`);
}
if (api.includes("access_token") || callback.includes("access_token")) throw new Error("token exposed in frontend contract");
console.log("Meta OAuth callback/binding frontend contract verification passed");
