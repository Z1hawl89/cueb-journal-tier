/* 在真实 Zotero 父进程执行，由 test_install.py 提供隔离配置和真实 XPI。 */
(async function (config) {
  const { Zotero } = ChromeUtils.importESModule("chrome://zotero/content/zotero.mjs");
  const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
  const { setTimeout, clearTimeout } = ChromeUtils.importESModule("resource://gre/modules/Timer.sys.mjs");
  await Zotero.initializationPromise;
  const normalizePath = p => String(p).replace(/\\/g, "/").toLowerCase().replace(/\/$/, "");
  function check(value, message) { if (!value) throw new Error(message); }
  check(Zotero.version === "10.0.6", "本验收要求真实 Zotero 10.0.6");
  check(normalizePath(Zotero.DataDirectory.dir) === normalizePath(config.dataDir), "数据目录未隔离");
  check(normalizePath(PathUtils.profileDir) === normalizePath(config.profile), "配置目录未隔离");
  const receipt = { phase: config.phase, zoteroVersion: Zotero.version,
    profile: PathUtils.profileDir, dataDirectory: Zotero.DataDirectory.dir, checks: [] };
  const columns = () => Zotero.ItemTreeManager.getCustomColumns().filter(c => c.pluginID === config.pluginID);
  async function until(predicate, label) {
    for (let i = 0; i < 100; i++) {
      if (predicate()) return;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error("超时: " + label);
  }
  if (config.phase === "install") {
    if (config.rejectedXpi) {
      let rejected = false;
      try {
        const oldInstall = await AddonManager.getInstallForFile(Zotero.File.pathToFile(config.rejectedXpi));
        rejected = !!oldInstall.error || !oldInstall.addon || !oldInstall.addon.isCompatible;
        receipt.oldPackageError = oldInstall.error;
      } catch (error) {
        rejected = true;
        receipt.oldPackageError = String(error);
      }
      check(rejected, "负向对照失败：旧1.0.9竟被安装器接受");
      receipt.checks.push("旧1.0.9被真实安装器拒绝");
    }
    const install = await AddonManager.getInstallForFile(Zotero.File.pathToFile(config.xpi));
    check(!install.error && install.addon && install.addon.isCompatible, "修正版解析或兼容性检查失败: " + install.error);
    await new Promise((resolve, reject) => {
      install.addListener({
        onInstallEnded(_install, addon) { resolve(addon); },
        onInstallFailed(i) { reject(new Error("onInstallFailed: " + i.error)); },
        onDownloadFailed(i) { reject(new Error("onDownloadFailed: " + i.error)); },
      });
      install.install().catch(reject);
    });
    receipt.checks.push("真实AddonManager安装成功");
  }
  const addon = await AddonManager.getAddonByID(config.pluginID);
  check(addon && addon.version === config.version && addon.isCompatible && addon.isActive, "插件未激活或版本不符");
  await until(() => columns().length === 1, "注册自定义列");
  receipt.addon = { id: addon.id, version: addon.version, isCompatible: addon.isCompatible, isActive: addon.isActive };
  receipt.checks.push("插件已激活且只注册一列");
  const key = columns()[0].dataKey;
  function value(pub, issn) {
    const item = new Zotero.Item("journalArticle");
    if (pub) item.setField("publicationTitle", pub);
    if (issn) item.setField("ISSN", issn);
    return Zotero.ItemTreeManager.getCustomCellData(item, key);
  }
  const samples = {
    managementScience: value("Management Science", ""),
    chineseIssn: value("", "1007-9807"),
    conflict: value("Journal of Business Ethics", "0025-1909"),
    aos: value("Accounting, Organizations and Society", ""),
  };
  check(samples.managementScience === "国际A+｜UTD24｜FT50｜ABS 4*", "公开数据样例不符");
  check(samples.chineseIssn === "中文A2｜CSSCI｜CSCD", "中文ISSN样例不符: " + JSON.stringify(samples));
  check(samples.conflict === samples.managementScience, "ISSN冲突优先级不符");
  check(samples.aos === "国际A1｜FT50｜ABS 4*", "AOS等级不符");
  receipt.samples = samples;
  receipt.checks.push("真实Zotero条目的等级和标签正确，未显示SSCI/JCR");
  if (config.phase === "install") {
    await addon.disable();
    await until(() => columns().length === 0, "禁用后注销列");
    await addon.enable();
    await until(() => columns().length === 1, "重启用后注册列");
    receipt.checks.push("禁用/重新启用成功，列无残留或重复");
  }
  if (config.phase === "update") {
    const outcome = await new Promise((resolve, reject) => {
      let noUpdate = false;
      const timer = setTimeout(() => reject(new Error("更新检查超时")), 30000);
      addon.findUpdates({
        onNoUpdateAvailable() { noUpdate = true; },
        onUpdateAvailable(_addon, install) { receipt.availableVersion = install.version; },
        onUpdateFinished(_addon, status) {
          clearTimeout(timer);
          if (status) reject(new Error("真实更新检查失败: " + status));
          else resolve({ status, noUpdate });
        }
      }, AddonManager.UPDATE_WHEN_USER_REQUESTED);
    });
    check(outcome.noUpdate, "当前版本的更新检查应报告已是最新");
    receipt.update = outcome;
    receipt.checks.push("真实Zotero成功读取线上更新清单，确认当前版本最新");
  }
  receipt.ok = true;
  return JSON.stringify(receipt);
})(__CONFIG__)
