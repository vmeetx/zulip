export default {
    plugins: [
        [
            "formatjs",
            {
                additionalFunctionNames: ["$t", "$t_html"],
                overrideIdFn: (_id, defaultMessage) => defaultMessage,
            },
        ],
    ],
    presets: [
        [
            "@babel/preset-env",
            {
                corejs: "3.45",
                shippedProposals: true,
                useBuiltIns: "usage",
            },
        ],
        "@babel/typescript",
    ],
};
