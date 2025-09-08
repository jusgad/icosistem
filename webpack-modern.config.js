const path = require('path');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const CssMinimizerPlugin = require('css-minimizer-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');
const { CleanWebpackPlugin } = require('clean-webpack-plugin');
const CopyWebpackPlugin = require('copy-webpack-plugin');
const HtmlWebpackPlugin = require('html-webpack-plugin');

const isProduction = process.env.NODE_ENV === 'production';

module.exports = {
  mode: isProduction ? 'production' : 'development',
  
  entry: {
    main: './app/static/src/js/main-modern.js',
    admin: './app/static/src/js/admin.js',
    auth: './app/static/src/js/auth.js',
    dashboard: './app/static/src/js/dashboard.js',
    styles: './app/static/src/scss/main.scss'
  },
  
  output: {
    path: path.resolve(__dirname, 'app/static/dist'),
    filename: isProduction ? 'js/[name].[contenthash:8].js' : 'js/[name].js',
    chunkFilename: isProduction ? 'js/[name].[contenthash:8].chunk.js' : 'js/[name].chunk.js',
    publicPath: '/static/dist/',
    clean: true,
    // Modern output format
    module: true,
    environment: {
      arrowFunction: true,
      const: true,
      destructuring: true,
      dynamicImport: true,
      forOf: true,
      module: true
    }
  },
  
  experiments: {
    outputModule: true
  },
  
  target: ['web', 'es2020'],
  
  module: {
    rules: [
      {
        test: /\.m?js$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: [
              ['@babel/preset-env', {
                targets: {
                  browsers: ['defaults', 'not IE 11', '> 1%', 'last 2 versions']
                },
                modules: false, // Let webpack handle modules
                useBuiltIns: 'usage',
                corejs: 3
              }]
            ],
            plugins: [
              '@babel/plugin-transform-runtime',
              '@babel/plugin-proposal-class-properties',
              '@babel/plugin-proposal-private-methods',
              ['@babel/plugin-proposal-decorators', { decoratorsBeforeExport: true }],
              '@babel/plugin-proposal-optional-chaining',
              '@babel/plugin-proposal-nullish-coalescing-operator'
            ]
          }
        }
      },
      {
        test: /\.(scss|sass|css)$/,
        use: [
          isProduction ? MiniCssExtractPlugin.loader : 'style-loader',
          {
            loader: 'css-loader',
            options: {
              importLoaders: 2,
              sourceMap: !isProduction
            }
          },
          {
            loader: 'postcss-loader',
            options: {
              postcssOptions: {
                plugins: [
                  ['autoprefixer'],
                  isProduction ? ['cssnano', { preset: 'default' }] : null
                ].filter(Boolean)
              },
              sourceMap: !isProduction
            }
          },
          {
            loader: 'sass-loader',
            options: {
              sourceMap: !isProduction,
              sassOptions: {
                includePaths: ['node_modules']
              }
            }
          }
        ]
      },
      {
        test: /\.(png|jpg|jpeg|gif|svg)$/i,
        type: 'asset',
        parser: {
          dataUrlCondition: {
            maxSize: 8 * 1024 // 8kb
          }
        },
        generator: {
          filename: 'images/[name].[hash:8][ext]'
        },
        use: [
          {
            loader: 'image-webpack-loader',
            options: {
              mozjpeg: { progressive: true, quality: 80 },
              optipng: { enabled: false },
              pngquant: { quality: [0.65, 0.90], speed: 4 },
              gifsicle: { interlaced: false },
              webp: { quality: 80 }
            }
          }
        ]
      },
      {
        test: /\.(woff|woff2|eot|ttf|otf)$/i,
        type: 'asset/resource',
        generator: {
          filename: 'fonts/[name].[hash:8][ext]'
        }
      },
      {
        test: /\.(mp4|webm|ogg|mp3|wav|flac|aac)$/i,
        type: 'asset/resource',
        generator: {
          filename: 'media/[name].[hash:8][ext]'
        }
      }
    ]
  },
  
  plugins: [
    new CleanWebpackPlugin(),
    
    new MiniCssExtractPlugin({
      filename: isProduction ? 'css/[name].[contenthash:8].css' : 'css/[name].css',
      chunkFilename: isProduction ? 'css/[name].[contenthash:8].chunk.css' : 'css/[name].chunk.css'
    }),
    
    new CopyWebpackPlugin({
      patterns: [
        {
          from: 'app/static/src/images',
          to: 'images',
          noErrorOnMissing: true
        },
        {
          from: 'app/static/src/fonts',
          to: 'fonts', 
          noErrorOnMissing: true
        },
        {
          from: 'app/static/src/manifest.json',
          to: 'manifest.json',
          noErrorOnMissing: true
        },
        {
          from: 'app/static/src/sw.js',
          to: 'sw.js',
          noErrorOnMissing: true
        }
      ]
    }),

    // Generate HTML files with proper module loading
    new HtmlWebpackPlugin({
      template: 'app/templates/base-modern.html',
      filename: '../templates/base-webpack.html',
      inject: 'head',
      scriptLoading: 'module',
      chunks: ['main', 'styles']
    })
  ],
  
  optimization: {
    minimize: isProduction,
    minimizer: [
      new TerserPlugin({
        terserOptions: {
          ecma: 2020,
          module: true,
          compress: {
            drop_console: isProduction,
            drop_debugger: true,
            pure_funcs: isProduction ? ['console.log', 'console.debug'] : []
          },
          format: {
            comments: false
          }
        },
        extractComments: false
      }),
      new CssMinimizerPlugin()
    ],
    
    splitChunks: {
      chunks: 'all',
      cacheGroups: {
        vendor: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          chunks: 'all',
          priority: 20,
          reuseExistingChunk: true
        },
        common: {
          name: 'common',
          minChunks: 2,
          chunks: 'all',
          priority: 10,
          reuseExistingChunk: true,
          enforce: true
        },
        modules: {
          test: /[\\/]app[\\/]static[\\/]src[\\/]js[\\/]modules[\\/]/,
          name: 'modules',
          chunks: 'all',
          priority: 15,
          reuseExistingChunk: true
        }
      }
    },
    
    runtimeChunk: {
      name: 'runtime'
    },

    // Modern tree shaking
    usedExports: true,
    sideEffects: false
  },
  
  resolve: {
    extensions: ['.js', '.mjs', '.jsx', '.json'],
    alias: {
      '@': path.resolve(__dirname, 'app/static/src'),
      '@js': path.resolve(__dirname, 'app/static/src/js'),
      '@modules': path.resolve(__dirname, 'app/static/src/js/modules'),
      '@services': path.resolve(__dirname, 'app/static/src/js/services'),
      '@utils': path.resolve(__dirname, 'app/static/src/js/utils'),
      '@css': path.resolve(__dirname, 'app/static/src/scss'),
      '@images': path.resolve(__dirname, 'app/static/src/images'),
      '@components': path.resolve(__dirname, 'app/static/src/js/components')
    },
    // Modern resolve options
    mainFields: ['browser', 'module', 'main'],
    conditionNames: ['import', 'module', 'require']
  },
  
  devtool: isProduction ? 'source-map' : 'eval-cheap-module-source-map',
  
  devServer: {
    static: {
      directory: path.join(__dirname, 'app/static/dist')
    },
    compress: true,
    port: 3000,
    hot: true,
    open: true,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        secure: false
      },
      '/auth': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        secure: false
      }
    },
    historyApiFallback: {
      rewrites: [
        { from: /^\/$/, to: '/static/dist/index.html' }
      ]
    },
    client: {
      overlay: {
        errors: true,
        warnings: false
      },
      progress: true
    }
  },
  
  performance: {
    maxAssetSize: 512000,
    maxEntrypointSize: 512000,
    hints: isProduction ? 'warning' : false
  },
  
  stats: {
    colors: true,
    modules: false,
    children: false,
    chunks: false,
    chunkModules: false,
    entrypoints: false,
    excludeAssets: /\.(map|txt|html)$/,
    assetsSort: '!size'
  },

  cache: {
    type: 'filesystem',
    cacheDirectory: path.resolve(__dirname, '.webpack-cache'),
    buildDependencies: {
      config: [__filename]
    }
  }
};