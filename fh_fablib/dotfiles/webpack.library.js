/*
Somewhat reusable webpack configuration chunks

A basic webpack file may looks as follows:

    module.exports = (env, argv) => {
      const { base, devServer, assetRule, postcssRule, babelWithPreactRule } =
        require("./webpack.library.js")(argv.mode === "production")

      return {
        ...base,
        devServer: devServer({ backendPort: env.backend }),
        module: {
          rules: [
            assetRule(),
            postcssRule({
              plugins: [
                "postcss-nested",
                ["postcss-custom-media", { importFrom: "./theme.config.js" }],
                "autoprefixer",
              ],
            }),
            babelWithPreactRule(),
          ],
        },
      }
    }

NOTE: PLEASE DO NOT EVER UPDATE THIS FILE WITHOUT CONTRIBUTING THE CHANGES BACK
TO FH-FABLIB AT https://github.com/feinheit/fh-fablib
*/

const path = require("path")
const MiniCssExtractPlugin = require("mini-css-extract-plugin")
const CssMinimizerPlugin = require("css-minimizer-webpack-plugin")
const HtmlWebpackPlugin = require("html-webpack-plugin")
const HtmlInlineScriptPlugin = require("html-inline-script-webpack-plugin")

const truthy = (...list) => list.filter((el) => !!el)

module.exports = (PRODUCTION) => {
  const cwd = process.cwd()

  function babelRule({ presets, plugins } = {}) {
    const options = {
      cacheDirectory: true,
      presets: [
        [
          "@babel/preset-env",
          { useBuiltIns: "usage", corejs: "3.21", targets: "defaults" },
        ],
      ],
      plugins: plugins || [],
    }
    if (presets) {
      options.presets = [...options.presets, ...presets]
    }
    if (plugins) {
      options.plugins = plugins
    }
    return {
      test: /\.m?js$/,
      exclude: /(node_modules)/,
      use: {
        loader: "babel-loader",
        options,
      },
    }
  }

  function miniCssExtractPlugin() {
    return new MiniCssExtractPlugin({
      filename: PRODUCTION ? "[name].[contenthash].css" : "[name].css",
    })
  }

  function htmlSingleChunkPlugin(chunk = "") {
    const debug = PRODUCTION ? "" : "debug."
    const config = {
      filename: `${debug}${chunk || "main"}.html`,
      templateContent: "<head></head>",
    }
    if (chunk) {
      config.filename = `${debug}${chunk}.html`
      config.chunks = [chunk]
    } else {
      config.filename = `${debug}[name].html`
    }
    return new HtmlWebpackPlugin(config)
  }

  function htmlInlineScriptPlugin() {
    return PRODUCTION
      ? new HtmlInlineScriptPlugin({
          scriptMatchPattern: [/runtime.*\.js$/],
        })
      : null
  }

  return {
    truthy,
    base: {
      mode: PRODUCTION ? "production" : "development",
      devtool: PRODUCTION ? "source-map" : "eval-source-map",
      context: path.join(cwd, "frontend"),
      entry: { main: "./main.js" },
      output: {
        clean: { keep: /\.html$/ },
        path: path.join(cwd, "static"),
        publicPath: "/static/",
        filename: PRODUCTION ? "[name].[contenthash].js" : "[name].js",
      },
      plugins: truthy(
        miniCssExtractPlugin(),
        htmlSingleChunkPlugin(),
        htmlInlineScriptPlugin()
      ),
      optimization: PRODUCTION
        ? {
            minimizer: ["...", new CssMinimizerPlugin()],
            runtimeChunk: "single",
            splitChunks: {
              chunks: "all",
            },
          }
        : {},
    },
    devServer({ backendPort }) {
      return {
        host: "0.0.0.0",
        port: 8000,
        allowedHosts: "all",
        devMiddleware: {
          index: true,
          writeToDisk: (path) => /\.html$/.test(path),
        },
        proxy: {
          context: () => true,
          target: `http://127.0.0.1:${backendPort}`,
        },
      }
    },
    assetRule() {
      return {
        test: /\.(png|woff2?|svg|eot|ttf|otf|gif|jpe?g)$/,
        type: "asset",
        parser: { dataUrlCondition: { maxSize: 512 /* bytes */ } },
      }
    },
    postcssRule({ plugins }) {
      plugins = plugins || ["autoprefixer"]
      return {
        test: /\.css$/i,
        use: [
          MiniCssExtractPlugin.loader,
          {
            loader: "css-loader",
          },
          {
            loader: "postcss-loader",
            options: {
              postcssOptions: { plugins },
            },
          },
        ],
      }
    },
    sassRule() {
      return {
        test: /\.scss$/i,
        use: [
          MiniCssExtractPlugin.loader,
          {
            loader: "css-loader",
          },
          {
            loader: "postcss-loader",
            options: {
              postcssOptions: { plugins: ["autoprefixer"] },
            },
          },
          {
            loader: "sass-loader",
            options: {
              sassOptions: {
                includePaths: [path.resolve(path.join(cwd, "node_modules"))],
              },
            },
          },
        ],
      }
    },
    babelRule,
    babelWithPreactRule() {
      return babelRule({
        plugins: [
          [
            "@babel/plugin-transform-react-jsx",
            { runtime: "automatic", importSource: "preact" },
          ],
        ],
      })
    },
    babelWithReactRule() {
      return babelRule({
        presets: [["@babel/preset-react", { runtime: "automatic" }]],
      })
    },
    miniCssExtractPlugin,
    htmlSingleChunkPlugin,
    htmlInlineScriptPlugin,
  }
}
