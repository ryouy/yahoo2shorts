const { execFileSync } = require('child_process')

exports.default = async (context) => {
  if (context.electronPlatformName !== 'darwin') return

  // Development builds do not have a Developer ID certificate.  Ad-hoc signing
  // keeps macOS from rejecting Electron's nested frameworks at launch.
  execFileSync('codesign', ['--force', '--deep', '--sign', '-', context.appOutDir + '/' + context.packager.appInfo.productFilename + '.app'], {
    stdio: 'inherit',
  })
}
