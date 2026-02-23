module.exports = {
  plugins: [
    ...(process.env.NODE_ENV === 'production'
      ? [
          require('cssnano')({
            preset: [
              'default',
              {
                discardComments: { removeAll: true },
                normalizeWhitespace: true,
                mergeLonghand: true,
                mergeRules: true,
                minifySelectors: true,
              },
            ],
          }),
        ]
      : []),
  ],
};
